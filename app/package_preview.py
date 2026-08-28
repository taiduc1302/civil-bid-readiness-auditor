"""Read-only semantic preview for an already verifiable review-package ZIP.

The preview is deliberately not a session-restoration path. It verifies the ZIP
first, parses only the package's known JSON/CSV evidence members in memory, checks
cross-member consistency, and returns bounded display data. No package member is
written to disk and no application session state is created or mutated here.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import Counter
from typing import Any

from finding_review import REVIEW_STATUSES, validate_disposition
from reference_validation import REFERENCE_STATUSES
from review_package import verify_review_package

PREVIEW_ROW_LIMIT = 100
_FINDING_FIELDS = (
    "id", "severity", "rule_id", "sheet", "row", "field", "message", "evidence", "recommended_action",
)
_REVIEW_FIELDS = _FINDING_FIELDS + ("review_status", "review_reason")
_REFERENCE_FIELDS = (
    "sheet", "source_row", "reference_type", "status", "code", "reference_code", "reference_unit", "message",
    "reference_filename", "reference_revision", "reference_size_bytes", "reference_sha256", "authority_status",
)
_SEVERITIES = ("Critical", "High", "Medium", "Low")
_EXPECTED_SAFETY = {
    "human_review_required": True,
    "bid_certified": False,
    "reference_authority_established_by_app": False,
    "heavybid_import_attempted": False,
    "NOT_PRODUCTION_READY": True,
    "NOT_ESTIMATOR_VALIDATED": True,
    "HEAVYBID_IMPORT_VALIDATED": False,
}


def _member(book: zipfile.ZipFile, name: str) -> bytes:
    try:
        return book.read(name)
    except (zipfile.BadZipFile, RuntimeError, KeyError, NotImplementedError, OSError) as exc:
        raise ValueError(f"Verified review package member could not be read for preview: {name}") from exc


def _json_object(book: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_member(book, name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Verified review package contains invalid preview JSON: {name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Verified review package preview requires a JSON object in {name}.")
    return value


def _csv_rows(book: zipfile.ZipFile, name: str, fields: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        text = _member(book, name).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        headers = tuple(reader.fieldnames or ())
        if headers != fields:
            raise ValueError(
                f"Verified review package {name} has unsupported columns; expected the package v1 schema."
            )
        rows: list[dict[str, str]] = []
        for row in reader:
            if None in row:
                raise ValueError(f"Verified review package {name} contains extra CSV columns.")
            rows.append({field: str(row.get(field, "") or "") for field in fields})
        return rows
    except csv.Error as exc:
        raise ValueError(f"Verified review package contains malformed CSV: {name}") from exc


def _positive_id(value: str, member: str) -> int:
    try:
        finding_id = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Verified review package {member} contains an invalid finding id.") from exc
    if finding_id <= 0:
        raise ValueError(f"Verified review package {member} contains an invalid finding id.")
    return finding_id


def _count_dict(value: Any, allowed: tuple[str, ...], label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"Verified review package manifest {label} must be an object.")
    result: dict[str, int] = {}
    for key in allowed:
        raw = value.get(key, 0)
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise ValueError(f"Verified review package manifest {label} contains an invalid count for {key}.")
        result[key] = raw
    unknown = [str(key) for key in value if key not in allowed]
    if unknown:
        raise ValueError(f"Verified review package manifest {label} contains unsupported keys.")
    return result


def _manifest_metadata_by_role(manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    value = manifest.get("reference_metadata", [])
    if not isinstance(value, list):
        raise ValueError("Verified review package manifest reference_metadata must be a list.")
    by_role: dict[str, dict[str, str]] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Verified review package manifest reference_metadata contains an invalid entry.")
        role = str(item.get("role", "")).strip().casefold()
        if role not in ("activity", "resource") or role in by_role:
            raise ValueError("Verified review package manifest reference metadata has an invalid or duplicate role.")
        by_role[role] = {
            "reference_filename": str(item.get("filename", "") or ""),
            "reference_revision": str(item.get("revision", "") or ""),
            "reference_size_bytes": str(item.get("size_bytes", "") if item.get("size_bytes", "") != "" else ""),
            "reference_sha256": str(item.get("sha256", "") or ""),
            "authority_status": str(item.get("authority_status", "") or ""),
        }
    return by_role


def inspect_verified_review_package(data: bytes, row_limit: int = PREVIEW_ROW_LIMIT) -> dict[str, Any]:
    """Verify then return a bounded, read-only semantic snapshot of package contents."""
    if not isinstance(row_limit, int) or isinstance(row_limit, bool) or row_limit <= 0 or row_limit > 1000:
        raise ValueError("Review package preview row limit must be an integer from 1 to 1000.")

    verified = verify_review_package(data)
    with zipfile.ZipFile(io.BytesIO(bytes(data)), "r") as book:
        manifest = _json_object(book, "manifest.json")
        findings = _csv_rows(book, "findings.csv", _FINDING_FIELDS)
        reviews = _csv_rows(book, "review.csv", _REVIEW_FIELDS)
        names = set(book.namelist())
        references = _csv_rows(book, "references.csv", _REFERENCE_FIELDS) if "references.csv" in names else []

    safety = manifest.get("safety")
    if not isinstance(safety, dict) or any(safety.get(key) is not expected for key, expected in _EXPECTED_SAFETY.items()):
        raise ValueError("Verified review package manifest safety state is not valid for read-only preview.")

    contents = manifest.get("contents")
    if not isinstance(contents, dict):
        raise ValueError("Verified review package manifest contents must be an object.")
    if contents.get("original_estimate_bytes_included") is not False or contents.get("original_reference_bytes_included") is not False:
        raise ValueError("Verified review package preview rejects packages that claim embedded original source bytes.")
    if contents.get("reference_checks_included") is not bool(references):
        raise ValueError("Verified review package manifest reference-check flag does not match package contents.")

    finding_by_id: dict[int, dict[str, str]] = {}
    for row in findings:
        finding_id = _positive_id(row["id"], "findings.csv")
        if finding_id in finding_by_id:
            raise ValueError("Verified review package findings.csv contains duplicate finding ids.")
        if row["severity"] not in _SEVERITIES:
            raise ValueError("Verified review package findings.csv contains an unsupported severity.")
        finding_by_id[finding_id] = row

    review_by_id: dict[int, dict[str, str]] = {}
    review_counts = Counter()
    severity_counts = Counter()
    for row in reviews:
        finding_id = _positive_id(row["id"], "review.csv")
        if finding_id in review_by_id:
            raise ValueError("Verified review package review.csv contains duplicate finding ids.")
        if row["severity"] not in _SEVERITIES:
            raise ValueError("Verified review package review.csv contains an unsupported severity.")
        try:
            status, reason = validate_disposition(row["review_status"], row["review_reason"])
        except ValueError as exc:
            raise ValueError("Verified review package review.csv contains an invalid review disposition.") from exc
        row["review_status"], row["review_reason"] = status, reason
        review_by_id[finding_id] = row
        review_counts[status] += 1
        severity_counts[row["severity"]] += 1

    if set(finding_by_id) != set(review_by_id):
        raise ValueError("Verified review package findings.csv and review.csv contain different finding ids.")
    for finding_id in sorted(finding_by_id):
        finding = finding_by_id[finding_id]
        review = review_by_id[finding_id]
        if any(finding[field] != review[field] for field in _FINDING_FIELDS):
            raise ValueError("Verified review package findings.csv and review.csv evidence does not match.")

    manifest_finding_counts = _count_dict(manifest.get("finding_counts", {}), _SEVERITIES, "finding_counts")
    if manifest_finding_counts != {key: severity_counts.get(key, 0) for key in _SEVERITIES}:
        raise ValueError("Verified review package manifest finding counts do not match review.csv.")
    manifest_review_counts = _count_dict(manifest.get("review_status_counts", {}), REVIEW_STATUSES, "review_status_counts")
    if manifest_review_counts != {key: review_counts.get(key, 0) for key in REVIEW_STATUSES}:
        raise ValueError("Verified review package manifest review-state counts do not match review.csv.")

    review_metrics = manifest.get("review_metrics", {})
    if not isinstance(review_metrics, dict) or review_metrics.get("finding_count") != len(reviews):
        raise ValueError("Verified review package manifest finding total does not match review.csv.")

    reference_counts = Counter()
    metadata_by_role = _manifest_metadata_by_role(manifest)
    for row in references:
        status = row["status"]
        role = row["reference_type"].strip().casefold()
        if status not in REFERENCE_STATUSES:
            raise ValueError("Verified review package references.csv contains an unsupported status.")
        if role not in ("activity", "resource"):
            raise ValueError("Verified review package references.csv contains an unsupported reference type.")
        reference_counts[status] += 1
        metadata = metadata_by_role.get(role)
        if metadata:
            for field, expected in metadata.items():
                if row[field] != expected:
                    raise ValueError("Verified review package reference metadata does not match references.csv.")

    manifest_reference_counts_raw = manifest.get("reference_status_counts", {})
    if not isinstance(manifest_reference_counts_raw, dict):
        raise ValueError("Verified review package manifest reference_status_counts must be an object.")
    if any(key not in REFERENCE_STATUSES for key in manifest_reference_counts_raw):
        raise ValueError("Verified review package manifest reference_status_counts contains unsupported keys.")
    normalized_reference_counts = {
        key: int(manifest_reference_counts_raw.get(key, 0)) for key in REFERENCE_STATUSES
    }
    if any(
        not isinstance(manifest_reference_counts_raw.get(key, 0), int)
        or isinstance(manifest_reference_counts_raw.get(key, 0), bool)
        or manifest_reference_counts_raw.get(key, 0) < 0
        for key in REFERENCE_STATUSES
    ):
        raise ValueError("Verified review package manifest reference_status_counts contains an invalid count.")
    if normalized_reference_counts != {key: reference_counts.get(key, 0) for key in REFERENCE_STATUSES}:
        raise ValueError("Verified review package manifest reference counts do not match references.csv.")

    source_filename = manifest.get("source_filename", "")
    sheets = manifest.get("sheets_reviewed", [])
    rows_reviewed = manifest.get("rows_reviewed", 0)
    if not isinstance(source_filename, str):
        raise ValueError("Verified review package manifest source_filename must be text.")
    if not isinstance(sheets, list) or not all(isinstance(item, str) for item in sheets):
        raise ValueError("Verified review package manifest sheets_reviewed must be a list of text values.")
    if not isinstance(rows_reviewed, int) or isinstance(rows_reviewed, bool) or rows_reviewed < 0:
        raise ValueError("Verified review package manifest rows_reviewed must be a nonnegative integer.")

    ordered_reviews = [review_by_id[finding_id] for finding_id in sorted(review_by_id)]
    return {
        "verified": dict(verified),
        "source_filename": source_filename,
        "rows_reviewed": rows_reviewed,
        "sheets_reviewed": list(sheets),
        "finding_total": len(ordered_reviews),
        "finding_rows": ordered_reviews[:row_limit],
        "findings_truncated": len(ordered_reviews) > row_limit,
        "review_status_counts": {key: review_counts.get(key, 0) for key in REVIEW_STATUSES},
        "reference_total": len(references),
        "reference_rows": references[:row_limit],
        "references_truncated": len(references) > row_limit,
        "reference_status_counts": {key: reference_counts.get(key, 0) for key in REFERENCE_STATUSES},
        "reference_metadata": list(manifest.get("reference_metadata", [])),
        "safety": dict(safety),
        "row_limit": row_limit,
        "session_restored": False,
    }
