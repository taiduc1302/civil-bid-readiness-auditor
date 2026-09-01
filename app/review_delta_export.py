"""Deterministic portable export for an already-verified Review Delta result."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from typing import Any, Iterable

DELTA_EXPORT_FORMAT = "civil-estimate-review-delta-export"
DELTA_EXPORT_VERSION = 1
DELTA_EXPORT_INTEGRITY_FORMAT = "civil-estimate-review-delta-export-integrity"
DELTA_EXPORT_INTEGRITY_VERSION = 1
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


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


def _write_member(book: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    book.writestr(info, data)


def build_review_delta_export(result: dict[str, Any]) -> tuple[bytes, str]:
    """Create byte-deterministic portable Review Delta evidence from one comparison result."""
    if result.get("comparison_format") != "civil-estimate-review-delta" or result.get("comparison_version") != 1:
        raise ValueError("Unsupported Review Delta comparison result.")
    for flag in ("session_created", "re_audit_performed", "correctness_inferred", "readiness_inferred", "heavybid_import_validated"):
        if result.get(flag) is not False:
            raise ValueError(f"Review Delta export requires {flag}=false.")

    members: dict[str, bytes] = {
        "manifest.json": _json_bytes(delta_export_manifest(result)),
        "review_delta.json": _json_bytes(result),
        "finding_changes.csv": _finding_csv(result),
        "reference_changes.csv": _reference_csv(result),
        "reference_metadata_changes.csv": _metadata_csv(result),
        "README.txt": (
            "Civil Estimate Review Auditor - Review Delta evidence export\n\n"
            "This bundle reports archived evidence drift only. It does not establish improvement, correctness, estimator approval, bid readiness, reference authority, or HeavyBid import validity.\n"
            "The original review-package, estimate, and reference bytes are not embedded. Operational Crew/Production session-only evidence is not part of review-package v1 and is not invented into this export.\n"
        ).encode("utf-8"),
    }
    members["integrity.json"] = _json_bytes(delta_export_integrity(members))

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as book:
        for name in sorted(members):
            _write_member(book, name, members[name])
    return output.getvalue(), "review_delta_evidence_v1.zip"
