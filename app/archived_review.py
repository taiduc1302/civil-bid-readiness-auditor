"""Archived review continuation derived from a verified review-package snapshot.

This module deliberately does not restore an estimate audit. Review-package v1
contains review evidence, not the original estimate/reference bytes. A
continuation session can therefore resume human finding dispositions and inspect
archived reference evidence, but it cannot remap columns, rerun deterministic
audit rules, or rerun governed references.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter
from typing import Any

from package_preview import inspect_review_package_members
from review_package import verify_review_package

ARCHIVED_REVIEW_SESSION_MODE = "archived_review_snapshot"
MAX_CONTINUATION_ROWS = 1000
_SEVERITY_WEIGHT = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
_FINDING_FIELDS = (
    "id", "severity", "rule_id", "sheet", "row", "field", "message", "evidence", "recommended_action",
)
_REFERENCE_CORE_FIELDS = (
    "sheet", "source_row", "reference_type", "status", "code", "reference_code", "reference_unit", "message",
)


def _manifest(data: bytes) -> dict[str, Any]:
    """Read manifest only after the caller has successfully verified the ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(bytes(data)), "r") as book:
            value = json.loads(book.read("manifest.json").decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, RuntimeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Verified review package manifest could not be read for archived continuation.") from exc
    if not isinstance(value, dict):
        raise ValueError("Verified review package manifest must be an object for archived continuation.")
    return value


def _source_session_mode(manifest: dict[str, Any]) -> str:
    context = manifest.get("session_context")
    if context is None:
        return "legacy_package_v1_unspecified"
    if not isinstance(context, dict):
        raise ValueError("Archived continuation rejects an invalid source session_context.")
    mode = str(context.get("mode", "") or "")
    if mode != ARCHIVED_REVIEW_SESSION_MODE:
        raise ValueError("Archived continuation rejects an unsupported source session mode.")
    required = {
        "continuation_only": True,
        "re_audit_performed": False,
        "original_estimate_bytes_available": False,
        "original_reference_bytes_available": False,
        "reference_rerun_available": False,
    }
    if any(context.get(key) is not expected for key, expected in required.items()):
        raise ValueError("Archived continuation rejects a source package with inconsistent continuation safety flags.")
    return mode


def _int_value(value: Any, label: str, *, allow_zero: bool = True) -> int:
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Archived review snapshot contains an invalid {label}.") from exc
    if result < 0 or (result == 0 and not allow_zero):
        raise ValueError(f"Archived review snapshot contains an invalid {label}.")
    return result


def build_archived_review_session(package_filename: str, data: bytes) -> dict[str, Any]:
    """Create a temporary review-only session from a verified package.

    No source package bytes are retained in the returned session. The caller may
    add its normal in-memory session timestamp before storing this object.
    """
    payload = bytes(data)
    verified = verify_review_package(payload)
    preview = verified.get("snapshot_preview") or {}
    finding_total = _int_value(preview.get("finding_total", 0), "finding total")
    reference_total = _int_value(preview.get("reference_total", 0), "reference total")
    if max(finding_total, reference_total) > MAX_CONTINUATION_ROWS:
        raise ValueError(
            f"Archived review continuation currently supports at most {MAX_CONTINUATION_ROWS} findings/reference checks per package; read-only verification remains available."
        )

    full = inspect_review_package_members(
        payload,
        verified,
        row_limit=max(1, finding_total, reference_total),
    )
    if full.get("findings_truncated") or full.get("references_truncated"):
        raise ValueError("Archived review continuation requires the complete verified snapshot evidence.")

    manifest = _manifest(payload)
    source_mode = _source_session_mode(manifest)

    findings: list[dict[str, Any]] = []
    dispositions: dict[int, dict[str, str]] = {}
    for archived in full.get("finding_rows", []):
        finding_id = _int_value(archived.get("id"), "finding id", allow_zero=False)
        source_row = _int_value(archived.get("row", 0), "finding source row")
        finding = {field: str(archived.get(field, "") or "") for field in _FINDING_FIELDS}
        finding["id"] = finding_id
        finding["row"] = source_row
        findings.append(finding)
        dispositions[finding_id] = {
            "status": str(archived.get("review_status", "") or ""),
            "reason": str(archived.get("review_reason", "") or ""),
        }

    counts = Counter(str(item.get("severity", "")) for item in findings)
    score = max(0, 100 - sum(_SEVERITY_WEIGHT.get(str(item.get("severity", "")), 0) for item in findings))
    affected = {(str(item.get("sheet", "")), int(item.get("row", 0))) for item in findings if int(item.get("row", 0)) > 0}
    priority = {
        (str(item.get("sheet", "")), int(item.get("row", 0)))
        for item in findings
        if int(item.get("row", 0)) > 0 and item.get("severity") in ("Critical", "High")
    }
    rows_reviewed = _int_value(full.get("rows_reviewed", 0), "rows reviewed")
    affected_percent = round((len(affected) / rows_reviewed * 100), 2) if rows_reviewed else 0.0
    review_metrics = {
        "status": "Archived review snapshot — no estimate re-audit performed",
        "finding_count": len(findings),
        "affected_rows": len(affected),
        "affected_row_percent": affected_percent,
        "priority_rows": len(priority),
        "summary_findings": sum(1 for item in findings if int(item.get("row", 0)) == 0),
    }
    result = {
        "findings": findings,
        "counts": {severity: counts.get(severity, 0) for severity in ("Critical", "High", "Medium", "Low")},
        "score": score,
        "rows_reviewed": rows_reviewed,
        "sheets_reviewed": list(full.get("sheets_reviewed", [])),
        "review_metrics": review_metrics,
        "score_explanation": (
            "Archived review snapshot compatibility score reconstructed only from the stored finding severities using the legacy weighting formula. "
            "The original estimate bytes are absent and deterministic audit rules were not rerun."
        ),
    }

    reference_results = [
        {field: str(item.get(field, "") or "") for field in _REFERENCE_CORE_FIELDS}
        for item in full.get("reference_rows", [])
    ]
    metadata = list(full.get("reference_metadata", []))
    reference_sources = manifest.get("reference_sources", [])
    if not isinstance(reference_sources, list) or not all(isinstance(item, str) for item in reference_sources):
        raise ValueError("Archived review snapshot contains invalid reference source metadata.")
    mappings = manifest.get("mappings", {})
    if not isinstance(mappings, dict):
        raise ValueError("Archived review snapshot contains invalid mapping evidence.")

    return {
        "session_mode": ARCHIVED_REVIEW_SESSION_MODE,
        "filename": str(full.get("source_filename", "") or "archived-review"),
        # Empty parsed source set makes any accidental legacy /audit POST fail closed
        # before it can replace the archived result. No audit_sheets key is present.
        "sheets": {},
        "result": result,
        "dispositions": dispositions,
        "mappings": mappings,
        "reference_results": reference_results,
        "reference_sources": list(reference_sources),
        "reference_metadata": metadata,
        "archived_snapshot_origin": {
            "package_filename": str(package_filename or "review-package.zip"),
            "package_sha256": hashlib.sha256(payload).hexdigest(),
            "package_format": str(verified.get("package_format", "")),
            "package_version": int(verified.get("package_version", 0)),
            "integrity_version": int(verified.get("integrity_version", 0)),
            "source_session_mode": source_mode,
            "continuation_only": True,
            "re_audit_performed": False,
            "original_estimate_bytes_available": False,
            "original_reference_bytes_available": False,
            "reference_rerun_available": False,
        },
    }


def archived_session_context(session: dict[str, Any]) -> dict[str, Any] | None:
    """Return deterministic manifest provenance for a re-exported archived review."""
    if session.get("session_mode") != ARCHIVED_REVIEW_SESSION_MODE:
        return None
    origin = session.get("archived_snapshot_origin")
    if not isinstance(origin, dict):
        raise ValueError("Archived review session is missing verified snapshot provenance.")
    return {
        "mode": ARCHIVED_REVIEW_SESSION_MODE,
        "continuation_only": True,
        "re_audit_performed": False,
        "original_estimate_bytes_available": False,
        "original_reference_bytes_available": False,
        "reference_rerun_available": False,
        "source_package_filename": str(origin.get("package_filename", "")),
        "source_package_sha256": str(origin.get("package_sha256", "")),
        "source_package_format": str(origin.get("package_format", "")),
        "source_package_version": int(origin.get("package_version", 0)),
        "source_package_integrity_version": int(origin.get("integrity_version", 0)),
        "source_package_session_mode": str(origin.get("source_session_mode", "")),
    }
