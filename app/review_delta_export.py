"""Deterministic portable export and strict verification for Review Delta evidence."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import PurePosixPath
from typing import Any, Iterable

DELTA_EXPORT_FORMAT = "civil-estimate-review-delta-export"
DELTA_EXPORT_VERSION = 1
DELTA_EXPORT_INTEGRITY_FORMAT = "civil-estimate-review-delta-export-integrity"
DELTA_EXPORT_INTEGRITY_VERSION = 1
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_REQUIRED_MEMBERS = {
    "README.txt",
    "finding_changes.csv",
    "integrity.json",
    "manifest.json",
    "reference_changes.csv",
    "reference_metadata_changes.csv",
    "review_delta.json",
}
_FINDING_CHANGE_TYPES = (
    "UNCHANGED",
    "REVIEW_CHANGED",
    "EVIDENCE_CHANGED",
    "EVIDENCE_AND_REVIEW_CHANGED",
    "ADDED",
    "REMOVED",
)
_REFERENCE_CHANGE_TYPES = ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")
_METADATA_CHANGE_TYPES = ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")
MAX_DELTA_EXPORT_BYTES = 50 * 1024 * 1024
MAX_DELTA_MEMBER_BYTES = 25 * 1024 * 1024
MAX_DELTA_TOTAL_UNCOMPRESSED_BYTES = 75 * 1024 * 1024


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_csv(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def _write_csv(fields: list[str], rows: Iterable[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _safe_csv(row.get(field, "")) for field in fields})
    return output.getvalue().encode("utf-8")


def _finding_csv(result: dict[str, Any]) -> bytes:
    fields = [
        "change_type", "sheet", "row", "rule_id", "field",
        "evidence_fields_changed", "review_fields_changed",
        "before_severity", "after_severity",
        "before_message", "after_message",
        "before_evidence", "after_evidence",
        "before_recommended_action", "after_recommended_action",
        "before_review_status", "after_review_status",
        "before_review_reason", "after_review_reason",
    ]
    rows: list[dict[str, Any]] = []
    for item in result.get("finding_changes", []):
        anchor = item.get("anchor", {})
        before = item.get("before") or {}
        after = item.get("after") or {}
        before_review = item.get("before_review") or {}
        after_review = item.get("after_review") or {}
        rows.append({
            "change_type": item.get("change_type", ""),
            "sheet": anchor.get("sheet", ""),
            "row": anchor.get("row", ""),
            "rule_id": anchor.get("rule_id", ""),
            "field": anchor.get("field", ""),
            "evidence_fields_changed": ",".join(item.get("evidence_fields_changed", [])),
            "review_fields_changed": ",".join(item.get("review_fields_changed", [])),
            "before_severity": before.get("severity", ""),
            "after_severity": after.get("severity", ""),
            "before_message": before.get("message", ""),
            "after_message": after.get("message", ""),
            "before_evidence": before.get("evidence", ""),
            "after_evidence": after.get("evidence", ""),
            "before_recommended_action": before.get("recommended_action", ""),
            "after_recommended_action": after.get("recommended_action", ""),
            "before_review_status": before_review.get("status", ""),
            "after_review_status": after_review.get("status", ""),
            "before_review_reason": before_review.get("reason", ""),
            "after_review_reason": after_review.get("reason", ""),
        })
    return _write_csv(fields, rows)


def _reference_csv(result: dict[str, Any]) -> bytes:
    fields = [
        "change_type", "reference_type", "sheet", "source_row", "code", "fields_changed",
        "before_status", "after_status", "before_reference_code", "after_reference_code",
        "before_reference_unit", "after_reference_unit", "before_message", "after_message",
    ]
    rows: list[dict[str, Any]] = []
    for item in result.get("reference_changes", []):
        anchor = item.get("anchor", {})
        before = item.get("before") or {}
        after = item.get("after") or {}
        rows.append({
            "change_type": item.get("change_type", ""),
            "reference_type": anchor.get("reference_type", ""),
            "sheet": anchor.get("sheet", ""),
            "source_row": anchor.get("source_row", ""),
            "code": anchor.get("code", ""),
            "fields_changed": ",".join(item.get("fields_changed", [])),
            "before_status": before.get("status", ""),
            "after_status": after.get("status", ""),
            "before_reference_code": before.get("reference_code", ""),
            "after_reference_code": after.get("reference_code", ""),
            "before_reference_unit": before.get("reference_unit", ""),
            "after_reference_unit": after.get("reference_unit", ""),
            "before_message": before.get("message", ""),
            "after_message": after.get("message", ""),
        })
    return _write_csv(fields, rows)


def _metadata_csv(result: dict[str, Any]) -> bytes:
    fields = [
        "change_type", "role", "fields_changed",
        "before_filename", "after_filename", "before_revision", "after_revision",
        "before_size_bytes", "after_size_bytes", "before_sha256", "after_sha256",
        "before_authority_status", "after_authority_status",
    ]
    rows: list[dict[str, Any]] = []
    for item in result.get("reference_metadata_changes", []):
        before = item.get("before") or {}
        after = item.get("after") or {}
        rows.append({
            "change_type": item.get("change_type", ""),
            "role": item.get("role", ""),
            "fields_changed": ",".join(item.get("fields_changed", [])),
            "before_filename": before.get("filename", ""),
            "after_filename": after.get("filename", ""),
            "before_revision": before.get("revision", ""),
            "after_revision": after.get("revision", ""),
            "before_size_bytes": before.get("size_bytes", ""),
            "after_size_bytes": after.get("size_bytes", ""),
            "before_sha256": before.get("sha256", ""),
            "after_sha256": after.get("sha256", ""),
            "before_authority_status": before.get("authority_status", ""),
            "after_authority_status": after.get("authority_status", ""),
        })
    return _write_csv(fields, rows)


def _readme_bytes() -> bytes:
    return (
        "Civil Estimate Review Auditor - Review Delta evidence export\n\n"
        "This bundle reports archived evidence drift only. It does not establish improvement, correctness, estimator approval, bid readiness, reference authority, or HeavyBid import validity.\n"
        "The original review-package, estimate, and reference bytes are not embedded. Operational Crew/Production session-only evidence is not part of review-package v1 and is not invented into this export.\n"
    ).encode("utf-8")


def delta_export_manifest(result: dict[str, Any]) -> dict[str, Any]:
    """Return the small portable-export contract without duplicating full evidence rows."""
    return {
        "export_format": DELTA_EXPORT_FORMAT,
        "export_version": DELTA_EXPORT_VERSION,
        "comparison_format": str(result.get("comparison_format", "")),
        "comparison_version": int(result.get("comparison_version", 0)),
        "earlier": dict(result.get("earlier", {})),
        "later": dict(result.get("later", {})),
        "same_source_filename": bool(result.get("same_source_filename", False)),
        "same_package_sha256": bool(result.get("same_package_sha256", False)),
        "finding_counts": dict(result.get("finding_counts", {})),
        "reference_counts": dict(result.get("reference_counts", {})),
        "reference_metadata_counts": dict(result.get("reference_metadata_counts", {})),
        "contents": {
            "full_comparison_json": "review_delta.json",
            "finding_delta_csv": "finding_changes.csv",
            "reference_delta_csv": "reference_changes.csv",
            "reference_metadata_delta_csv": "reference_metadata_changes.csv",
            "original_review_packages_included": False,
            "original_estimate_reference_bytes_included": False,
            "operational_session_evidence_included": False,
        },
        "safety": {
            "evidence_drift_only": True,
            "session_created": False,
            "re_audit_performed": False,
            "correctness_inferred": False,
            "readiness_inferred": False,
            "heavybid_import_validated": False,
        },
    }


def delta_export_integrity(members: dict[str, bytes]) -> dict[str, Any]:
    return {
        "integrity_format": DELTA_EXPORT_INTEGRITY_FORMAT,
        "integrity_version": DELTA_EXPORT_INTEGRITY_VERSION,
        "export_format": DELTA_EXPORT_FORMAT,
        "export_version": DELTA_EXPORT_VERSION,
        "members": {
            name: {"size_bytes": len(data), "sha256": _sha256(data)}
            for name, data in sorted(members.items())
        },
    }


def _counter(rows: list[dict[str, Any]], allowed: tuple[str, ...], label: str) -> dict[str, int]:
    counts = Counter()
    for item in rows:
        change_type = item.get("change_type")
        if change_type not in allowed:
            raise ValueError(f"Review Delta comparison contains unsupported {label} change type: {change_type}")
        counts[change_type] += 1
    return {key: counts.get(key, 0) for key in allowed}


def _validate_unique_anchors(result: dict[str, Any]) -> None:
    finding_seen: set[tuple[str, int, str, str]] = set()
    for item in result["finding_changes"]:
        anchor = item.get("anchor")
        if not isinstance(anchor, dict):
            raise ValueError("Review Delta comparison finding anchor must be an object.")
        row = anchor.get("row")
        if not isinstance(row, int) or isinstance(row, bool):
            raise ValueError("Review Delta comparison finding anchor row must be an integer.")
        values = (anchor.get("sheet"), anchor.get("rule_id"), anchor.get("field"))
        if not all(isinstance(value, str) for value in values):
            raise ValueError("Review Delta comparison finding anchor fields must be strings.")
        key = (values[0], row, values[1], values[2])
        if key in finding_seen:
            raise ValueError(f"Review Delta export contains duplicate finding anchor: {key!r}")
        finding_seen.add(key)
        for field in ("evidence_fields_changed", "review_fields_changed"):
            value = item.get(field)
            if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
                raise ValueError(f"Review Delta comparison finding field must be a list of strings: {field}")

    reference_seen: set[tuple[str, str, str, str]] = set()
    for item in result["reference_changes"]:
        anchor = item.get("anchor")
        if not isinstance(anchor, dict):
            raise ValueError("Review Delta comparison reference anchor must be an object.")
        values = tuple(anchor.get(field) for field in ("reference_type", "sheet", "source_row", "code"))
        if not all(isinstance(value, str) for value in values):
            raise ValueError("Review Delta comparison reference anchor fields must be strings.")
        if values in reference_seen:
            raise ValueError(f"Review Delta export contains duplicate reference anchor: {values!r}")
        reference_seen.add(values)
        fields_changed = item.get("fields_changed")
        if not isinstance(fields_changed, list) or not all(isinstance(entry, str) for entry in fields_changed):
            raise ValueError("Review Delta comparison reference fields_changed must be a list of strings.")

    metadata_seen: set[str] = set()
    for item in result["reference_metadata_changes"]:
        role = item.get("role")
        if role not in ("activity", "resource"):
            raise ValueError("Review Delta comparison contains unsupported reference metadata role.")
        if role in metadata_seen:
            raise ValueError(f"Review Delta export contains duplicate reference metadata role: {role}")
        metadata_seen.add(role)
        fields_changed = item.get("fields_changed")
        if not isinstance(fields_changed, list) or not all(isinstance(entry, str) for entry in fields_changed):
            raise ValueError("Review Delta comparison metadata fields_changed must be a list of strings.")


def _validate_comparison_result(result: dict[str, Any]) -> None:
    version = result.get("comparison_version")
    if result.get("comparison_format") != "civil-estimate-review-delta" or version != 1 or isinstance(version, bool):
        raise ValueError("Unsupported Review Delta comparison result.")
    for field in ("earlier", "later", "finding_counts", "reference_counts", "reference_metadata_counts"):
        if not isinstance(result.get(field), dict):
            raise ValueError(f"Review Delta comparison field must be an object: {field}")
    for field in ("finding_changes", "reference_changes", "reference_metadata_changes"):
        value = result.get(field)
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError(f"Review Delta comparison field must be a list of objects: {field}")
    for flag in ("same_source_filename", "same_package_sha256"):
        if not isinstance(result.get(flag), bool):
            raise ValueError(f"Review Delta comparison field must be boolean: {flag}")
    for flag in ("session_created", "re_audit_performed", "correctness_inferred", "readiness_inferred", "heavybid_import_validated"):
        if result.get(flag) is not False:
            raise ValueError(f"Review Delta export requires {flag}=false.")

    _validate_unique_anchors(result)
    finding_counts = _counter(result["finding_changes"], _FINDING_CHANGE_TYPES, "finding")
    reference_counts = _counter(result["reference_changes"], _REFERENCE_CHANGE_TYPES, "reference")
    metadata_counts = _counter(result["reference_metadata_changes"], _METADATA_CHANGE_TYPES, "reference metadata")
    if result["finding_counts"] != finding_counts:
        raise ValueError("Review Delta comparison finding_counts do not match finding change rows.")
    if result["reference_counts"] != reference_counts:
        raise ValueError("Review Delta comparison reference_counts do not match reference change rows.")
    if result["reference_metadata_counts"] != metadata_counts:
        raise ValueError("Review Delta comparison reference_metadata_counts do not match metadata change rows.")


def _write_member(book: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    book.writestr(info, data)


def build_review_delta_export(result: dict[str, Any]) -> tuple[bytes, str]:
    """Create byte-deterministic portable Review Delta evidence from one comparison result."""
    _validate_comparison_result(result)
    members: dict[str, bytes] = {
        "manifest.json": _json_bytes(delta_export_manifest(result)),
        "review_delta.json": _json_bytes(result),
        "finding_changes.csv": _finding_csv(result),
        "reference_changes.csv": _reference_csv(result),
        "reference_metadata_changes.csv": _metadata_csv(result),
        "README.txt": _readme_bytes(),
    }
    members["integrity.json"] = _json_bytes(delta_export_integrity(members))

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as book:
        for name in sorted(members):
            _write_member(book, name, members[name])
    return output.getvalue(), "review_delta_evidence_v1.zip"


def _validate_member_name(name: str) -> None:
    if not name or "\\" in name:
        raise ValueError("Review Delta export contains an invalid member name.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ValueError(f"Review Delta export contains an unsafe member path: {name}")


def _read_member(book: zipfile.ZipFile, name: str) -> bytes:
    try:
        return book.read(name)
    except (zipfile.BadZipFile, RuntimeError, KeyError, NotImplementedError, OSError) as exc:
        raise ValueError(f"Review Delta export member could not be read safely: {name}") from exc


def _read_json(book: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_member(book, name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Review Delta export contains invalid {name}.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Review Delta export {name} must contain a JSON object.")
    return value


def verify_review_delta_export(data: bytes) -> dict[str, Any]:
    """Verify ZIP structure, hashes, and deterministic semantic agreement in memory."""
    payload = bytes(data)
    if not payload:
        raise ValueError("Review Delta export is blank.")
    if len(payload) > MAX_DELTA_EXPORT_BYTES:
        raise ValueError("Review Delta export exceeds the 50 MB verification limit.")
    try:
        book = zipfile.ZipFile(io.BytesIO(payload), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Review Delta export is not a readable ZIP archive.") from exc

    with book:
        infos = book.infolist()
        for info in infos:
            if info.is_dir():
                raise ValueError(f"Review Delta export contains unsupported directory entry: {info.filename}")
            _validate_member_name(info.filename)
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("Review Delta export contains duplicate member names.")
        member_set = set(names)
        missing = sorted(_REQUIRED_MEMBERS - member_set)
        if missing:
            raise ValueError(f"Review Delta export is missing required members: {', '.join(missing)}")
        unexpected = sorted(member_set - _REQUIRED_MEMBERS)
        if unexpected:
            raise ValueError(f"Review Delta export contains unexpected members: {', '.join(unexpected)}")

        total_uncompressed = 0
        for info in infos:
            if info.file_size > MAX_DELTA_MEMBER_BYTES:
                raise ValueError(f"Review Delta export member exceeds the 25 MB verification limit: {info.filename}")
            total_uncompressed += info.file_size
        if total_uncompressed > MAX_DELTA_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("Review Delta export exceeds the 75 MB uncompressed verification limit.")

        integrity = _read_json(book, "integrity.json")
        if integrity.get("integrity_format") != DELTA_EXPORT_INTEGRITY_FORMAT or integrity.get("integrity_version") != DELTA_EXPORT_INTEGRITY_VERSION:
            raise ValueError("Review Delta export integrity contract is unsupported.")
        if integrity.get("export_format") != DELTA_EXPORT_FORMAT or integrity.get("export_version") != DELTA_EXPORT_VERSION:
            raise ValueError("Review Delta export integrity metadata has unsupported export identity.")
        expected = integrity.get("members")
        if not isinstance(expected, dict):
            raise ValueError("Review Delta export integrity metadata is missing member checksums.")
        actual_names = member_set - {"integrity.json"}
        if set(expected) != actual_names:
            raise ValueError("Review Delta export integrity member list does not match archive contents.")
        for name in sorted(actual_names):
            entry = expected.get(name)
            if not isinstance(entry, dict):
                raise ValueError(f"Review Delta export integrity entry is invalid: {name}")
            expected_sha = str(entry.get("sha256", ""))
            expected_size = entry.get("size_bytes")
            if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
                raise ValueError(f"Review Delta export integrity SHA-256 is invalid: {name}")
            if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
                raise ValueError(f"Review Delta export integrity size is invalid: {name}")
            member_data = _read_member(book, name)
            if len(member_data) != expected_size:
                raise ValueError(f"Review Delta export member size does not match integrity metadata: {name}")
            if _sha256(member_data) != expected_sha:
                raise ValueError(f"Review Delta export member SHA-256 does not match integrity metadata: {name}")

        manifest = _read_json(book, "manifest.json")
        comparison = _read_json(book, "review_delta.json")
        _validate_comparison_result(comparison)
        if manifest.get("export_format") != DELTA_EXPORT_FORMAT or manifest.get("export_version") != DELTA_EXPORT_VERSION:
            raise ValueError("Review Delta export manifest identity is unsupported.")
        expected_manifest = delta_export_manifest(comparison)
        if manifest != expected_manifest:
            raise ValueError("Review Delta export manifest does not match the full comparison evidence.")

        try:
            expected_csvs = {
                "finding_changes.csv": _finding_csv(comparison),
                "reference_changes.csv": _reference_csv(comparison),
                "reference_metadata_changes.csv": _metadata_csv(comparison),
            }
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Review Delta export contains malformed comparison evidence.") from exc
        for name, expected_bytes in expected_csvs.items():
            if _read_member(book, name) != expected_bytes:
                raise ValueError(f"Review Delta export {name} does not match the full comparison evidence.")
        if _read_member(book, "README.txt") != _readme_bytes():
            raise ValueError("Review Delta export README does not match the supported safety contract.")

    changed_findings = [item for item in comparison["finding_changes"] if item.get("change_type") != "UNCHANGED"][:100]
    changed_references = [item for item in comparison["reference_changes"] if item.get("change_type") != "UNCHANGED"][:100]
    changed_metadata = [item for item in comparison["reference_metadata_changes"] if item.get("change_type") != "UNCHANGED"][:20]
    return {
        "valid": True,
        "export_format": DELTA_EXPORT_FORMAT,
        "export_version": DELTA_EXPORT_VERSION,
        "comparison_format": comparison["comparison_format"],
        "comparison_version": comparison["comparison_version"],
        "members_verified": len(actual_names),
        "earlier": dict(comparison["earlier"]),
        "later": dict(comparison["later"]),
        "finding_counts": dict(comparison["finding_counts"]),
        "reference_counts": dict(comparison["reference_counts"]),
        "reference_metadata_counts": dict(comparison["reference_metadata_counts"]),
        "preview": {
            "finding_changes": changed_findings,
            "reference_changes": changed_references,
            "reference_metadata_changes": changed_metadata,
        },
        "session_created": False,
        "re_audit_performed": False,
        "correctness_inferred": False,
        "readiness_inferred": False,
        "heavybid_import_validated": False,
    }
