"""Pure compatibility inspection for future review-package re-open work.

A compatible result means the integrity-verified package is internally
consistent with the current review-snapshot contract. It does NOT restore a
session, recreate source estimate/reference bytes, or infer approval/authority.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import Counter
from typing import Any

from finding_review import REVIEW_STATUSES, validate_disposition
from reference_metadata import REFERENCE_ROLES
from reference_validation import REFERENCE_STATUSES
from review_package import (
    INTEGRITY_VERSION,
    PACKAGE_FORMAT,
    PACKAGE_VERSION,
    verify_review_package,
)

COMPATIBILITY_FORMAT = "civil-estimate-review-reopen-compatibility"
COMPATIBILITY_VERSION = 1

_FINDING_FIELDS = [
    "id", "severity", "rule_id", "sheet", "row", "field", "message", "evidence", "recommended_action",
]
_REVIEW_FIELDS = _FINDING_FIELDS + ["review_status", "review_reason"]
_REFERENCE_FIELDS = [
    "sheet", "source_row", "reference_type", "status", "code", "reference_code", "reference_unit", "message",
    "reference_filename", "reference_revision", "reference_size_bytes", "reference_sha256", "authority_status",
]
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


def _read_member(book: zipfile.ZipFile, name: str) -> bytes:
    try:
        return book.read(name)
    except (zipfile.BadZipFile, RuntimeError, KeyError, NotImplementedError, OSError) as exc:
        raise ValueError(f"Review package compatibility member could not be read safely: {name}") from exc


def _read_json(book: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_member(book, name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Review package compatibility metadata is invalid: {name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Review package compatibility metadata must be an object: {name}")
    return value


def _read_csv(book: zipfile.ZipFile, name: str, expected_fields: list[str]) -> list[dict[str, str]]:
    try:
        text = _read_member(book, name).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Review package compatibility CSV must be UTF-8: {name}") from exc
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames != expected_fields:
            raise ValueError(
                f"Review package compatibility CSV header is unsupported: {name}; "
                f"expected {', '.join(expected_fields)}"
            )
        rows: list[dict[str, str]] = []
        for row in reader:
            if None in row:
                raise ValueError(f"Review package compatibility CSV row has extra columns: {name}")
            rows.append({field: str(row.get(field, "") or "") for field in expected_fields})
        return rows
    except csv.Error as exc:
        raise ValueError(f"Review package compatibility CSV could not be parsed: {name}") from exc


def _as_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Review package compatibility {label} must be a nonnegative integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Review package compatibility {label} must be a nonnegative integer.") from exc
    if parsed < 0:
        raise ValueError(f"Review package compatibility {label} must be a nonnegative integer.")
    return parsed


def _csv_safe(value: Any) -> str:
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def _validate_manifest(manifest: dict[str, Any], references_present: bool) -> tuple[int, list[str], dict[str, Any]]:
    if manifest.get("package_format") != PACKAGE_FORMAT or manifest.get("package_version") != PACKAGE_VERSION:
        raise ValueError("Review package compatibility manifest identity is unsupported.")

    rows_reviewed = _as_nonnegative_int(manifest.get("rows_reviewed"), "rows_reviewed")
    sheets = manifest.get("sheets_reviewed")
    if not isinstance(sheets, list) or any(not isinstance(item, str) or not item.strip() for item in sheets):
        raise ValueError("Review package compatibility sheets_reviewed is invalid.")
    if len(sheets) != len(set(sheets)) or sheets != sorted(sheets):
        raise ValueError("Review package compatibility sheets_reviewed must be unique and sorted.")

    mappings = manifest.get("mappings")
    if not isinstance(mappings, dict):
        raise ValueError("Review package compatibility mappings must be an object.")
    for sheet, mapping in mappings.items():
        if not isinstance(sheet, str) or not isinstance(mapping, dict):
            raise ValueError("Review package compatibility mapping structure is invalid.")
        if any(not isinstance(field, str) or not isinstance(column, str) for field, column in mapping.items()):
            raise ValueError("Review package compatibility mapping entries must be strings.")

    safety = manifest.get("safety")
    if safety != _EXPECTED_SAFETY:
        raise ValueError("Review package compatibility safety state is unsupported or relaxed.")

    contents = manifest.get("contents")
    if not isinstance(contents, dict):
        raise ValueError("Review package compatibility contents metadata is missing.")
    expected_contents = {
        "original_estimate_bytes_included": False,
        "original_reference_bytes_included": False,
        "reference_checks_included": references_present,
        "integrity_metadata_included": True,
    }
    for key, expected in expected_contents.items():
        if contents.get(key) is not expected:
            raise ValueError(f"Review package compatibility contents flag is inconsistent: {key}")

    metadata = manifest.get("reference_metadata")
    if not isinstance(metadata, list):
        raise ValueError("Review package compatibility reference_metadata must be a list.")
    metadata_included = bool(metadata)
    if contents.get("reference_metadata_included") is not metadata_included:
        raise ValueError("Review package compatibility reference_metadata_included flag is inconsistent.")
    if metadata_included and not references_present:
        raise ValueError("Review package compatibility contains reference metadata without reference checks.")

    return rows_reviewed, sheets, mappings


def _validate_findings_and_review(
    findings: list[dict[str, str]],
    review: list[dict[str, str]],
    manifest: dict[str, Any],
    rows_reviewed: int,
) -> None:
    if len(findings) != len(review):
        raise ValueError("Review package compatibility findings/review row counts differ.")

    ids: list[int] = []
    severity_counts: Counter[str] = Counter()
    review_counts: Counter[str] = Counter()
    affected: set[tuple[str, int]] = set()
    priority: set[tuple[str, int]] = set()
    summary_count = 0

    for finding_row, review_row in zip(findings, review):
        for field in _FINDING_FIELDS:
            if review_row[field] != finding_row[field]:
                raise ValueError(f"Review package compatibility findings/review evidence differs for field: {field}")
        try:
            finding_id = int(finding_row["id"])
        except ValueError as exc:
            raise ValueError("Review package compatibility finding id is invalid.") from exc
        if finding_id <= 0:
            raise ValueError("Review package compatibility finding id must be positive.")
        ids.append(finding_id)

        severity = finding_row["severity"]
        if severity not in _SEVERITIES:
            raise ValueError(f"Review package compatibility severity is unsupported: {severity}")
        severity_counts[severity] += 1
        if not finding_row["rule_id"] or not finding_row["sheet"]:
            raise ValueError("Review package compatibility finding identity is incomplete.")
        try:
            source_row = int(finding_row["row"])
        except ValueError as exc:
            raise ValueError("Review package compatibility finding row is invalid.") from exc
        if source_row < 0:
            raise ValueError("Review package compatibility finding row cannot be negative.")
        if source_row == 0:
            summary_count += 1
        else:
            location = (finding_row["sheet"], source_row)
            affected.add(location)
            if severity in ("Critical", "High"):
                priority.add(location)

        status, reason = validate_disposition(review_row["review_status"], review_row["review_reason"])
        if status != review_row["review_status"] or reason != review_row["review_reason"].strip():
            raise ValueError("Review package compatibility review disposition is not canonical.")
        review_counts[status] += 1

    if ids != list(range(1, len(ids) + 1)):
        raise ValueError("Review package compatibility finding ids must be unique, ordered, and contiguous from 1.")

    expected_finding_counts = {severity: severity_counts.get(severity, 0) for severity in _SEVERITIES}
    if manifest.get("finding_counts") != expected_finding_counts:
        raise ValueError("Review package compatibility finding counts do not match findings.csv.")
    expected_review_counts = {status: review_counts.get(status, 0) for status in REVIEW_STATUSES}
    if manifest.get("review_status_counts") != expected_review_counts:
        raise ValueError("Review package compatibility review status counts do not match review.csv.")

    metrics = manifest.get("review_metrics")
    if not isinstance(metrics, dict):
        raise ValueError("Review package compatibility review_metrics is invalid.")
    affected_percent = round((len(affected) / rows_reviewed * 100), 2) if rows_reviewed else 0.0
    if severity_counts["Critical"]:
        status_text = "Critical review required"
    elif severity_counts["High"]:
        status_text = "High-priority review required"
    elif severity_counts["Medium"]:
        status_text = "Review recommended"
    elif severity_counts["Low"]:
        status_text = "Minor review prompts"
    else:
        status_text = "No deterministic findings"
    expected_metrics = {
        "status": status_text,
        "finding_count": len(findings),
        "affected_rows": len(affected),
        "affected_row_percent": affected_percent,
        "priority_rows": len(priority),
        "summary_findings": summary_count,
    }
    if metrics != expected_metrics:
        raise ValueError("Review package compatibility review metrics do not match findings.csv.")


def _validate_reference_metadata(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metadata = manifest.get("reference_metadata", [])
    by_role: dict[str, dict[str, Any]] = {}
    for item in metadata:
        if not isinstance(item, dict):
            raise ValueError("Review package compatibility reference metadata entry is invalid.")
        role = str(item.get("role", "")).strip().casefold()
        if role not in REFERENCE_ROLES or role in by_role:
            raise ValueError("Review package compatibility reference metadata role is invalid or duplicated.")
        filename = item.get("filename")
        revision = item.get("revision")
        if not isinstance(filename, str) or not filename.strip() or not isinstance(revision, str) or len(revision) > 200:
            raise ValueError("Review package compatibility reference metadata filename/revision is invalid.")
        size = _as_nonnegative_int(item.get("size_bytes"), "reference size_bytes")
        sha = str(item.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("Review package compatibility reference SHA-256 is invalid.")
        if item.get("authority_status") != "NOT_ESTABLISHED_BY_APP":
            raise ValueError("Review package compatibility reference authority state is unsupported.")
        normalized = dict(item)
        normalized["size_bytes"] = size
        by_role[role] = normalized

    sources = manifest.get("reference_sources")
    if not isinstance(sources, list) or any(not isinstance(item, str) for item in sources):
        raise ValueError("Review package compatibility reference_sources is invalid.")
    expected_sources = [item["filename"] for item in metadata]
    if sources != expected_sources:
        raise ValueError("Review package compatibility reference sources do not match metadata.")
    return by_role


def _validate_references(
    rows: list[dict[str, str]], manifest: dict[str, Any], metadata_by_role: dict[str, dict[str, Any]]
) -> None:
    if not rows:
        raise ValueError("Review package compatibility references.csv is empty.")
    counts: Counter[str] = Counter()
    for row in rows:
        role = row["reference_type"].strip().casefold()
        if role not in REFERENCE_ROLES:
            raise ValueError("Review package compatibility reference type is unsupported.")
        status = row["status"]
        if status not in REFERENCE_STATUSES:
            raise ValueError("Review package compatibility reference status is unsupported.")
        counts[status] += 1
        try:
            source_row = int(row["source_row"])
        except ValueError as exc:
            raise ValueError("Review package compatibility reference source_row is invalid.") from exc
        if source_row <= 0 or not row["sheet"]:
            raise ValueError("Review package compatibility reference source linkage is invalid.")

        meta = metadata_by_role.get(role)
        if meta is None:
            raise ValueError("Review package compatibility reference check lacks governed evidence metadata.")
        expected_csv = {
            "reference_filename": _csv_safe(meta["filename"]),
            "reference_revision": _csv_safe(meta["revision"]),
            "reference_size_bytes": str(meta["size_bytes"]),
            "reference_sha256": meta["sha256"],
            "authority_status": "NOT_ESTABLISHED_BY_APP",
        }
        for field, expected in expected_csv.items():
            if row[field] != expected:
                raise ValueError(f"Review package compatibility reference evidence differs for field: {field}")

    expected_counts = dict(sorted((status, count) for status, count in counts.items() if status))
    if manifest.get("reference_status_counts") != expected_counts:
        raise ValueError("Review package compatibility reference status counts do not match references.csv.")


def inspect_reopen_compatibility(data: bytes) -> dict[str, Any]:
    """Return a compatibility report only; never restore or mutate review state."""
    payload = bytes(data)
    verified = verify_review_package(payload)

    try:
        book = zipfile.ZipFile(io.BytesIO(payload), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Review package compatibility inspection requires a readable ZIP archive.") from exc

    with book:
        names = set(book.namelist())
        references_present = "references.csv" in names
        manifest = _read_json(book, "manifest.json")
        rows_reviewed, sheets_reviewed, mappings = _validate_manifest(manifest, references_present)
        findings = _read_csv(book, "findings.csv", _FINDING_FIELDS)
        review = _read_csv(book, "review.csv", _REVIEW_FIELDS)
        _validate_findings_and_review(findings, review, manifest, rows_reviewed)

        metadata_by_role = _validate_reference_metadata(manifest)
        if references_present:
            references = _read_csv(book, "references.csv", _REFERENCE_FIELDS)
            _validate_references(references, manifest, metadata_by_role)
            reference_count = len(references)
        else:
            if metadata_by_role or manifest.get("reference_status_counts") or manifest.get("reference_sources"):
                raise ValueError("Review package compatibility reference manifest data exists without references.csv.")
            reference_count = 0

        source_filename = manifest.get("source_filename")
        if not isinstance(source_filename, str):
            raise ValueError("Review package compatibility source_filename is invalid.")

        return {
            "compatible": True,
            "compatibility_format": COMPATIBILITY_FORMAT,
            "compatibility_version": COMPATIBILITY_VERSION,
            "reopen_scope": "review_snapshot_only",
            "package_format": verified["package_format"],
            "package_version": verified["package_version"],
            "integrity_version": INTEGRITY_VERSION,
            "source_filename": source_filename,
            "rows_reviewed": rows_reviewed,
            "sheets_reviewed": list(sheets_reviewed),
            "finding_count": len(findings),
            "review_state_count": len(review),
            "reference_check_count": reference_count,
            "reference_metadata_count": len(metadata_by_role),
            "mappings_available": bool(mappings),
            "original_estimate_bytes_available": False,
            "original_reference_bytes_available": False,
            "audit_recomputation_supported": False,
            "session_restoration_supported": False,
            "session_restored": False,
            "approval_inferred": False,
            "reference_authority_inferred": False,
            "heavybid_import_validated": False,
        }
