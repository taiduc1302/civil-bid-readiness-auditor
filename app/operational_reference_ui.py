"""Explicit runtime integration for session-only operational Activity evidence.

This installer keeps Crew Code / Production Rate comparison separate from package-v1
reference evidence. It also invalidates operational UI state when the source-backed
audit selection/mapping changes, without changing deterministic audit behavior.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import reference_session as _reference_session
import server_legacy as _server
from reference_validation import canonicalize_export_rows

_OPERATIONAL_SESSION_KEYS = (
    "operational_reference_results",
    "operational_reference_metadata",
    "operational_reference_fields",
    "operational_source_fingerprint",
)
_REGULAR_UPLOAD_KEYS = ("activity_reference", "resource_reference")


def operational_source_fingerprint(session: dict[str, Any]) -> str:
    """Fingerprint only explicit Activity/Crew/Production source evidence and mapping."""
    if "audit_sheets" not in session:
        return ""
    mappings = session.get("mappings", {})
    normalized_mappings: dict[str, dict[str, str]] = {}
    eligible_sheets: set[str] = set()
    for sheet, mapping in mappings.items():
        operational = {
            field: str(mapping.get(field, "") or "")
            for field in ("activity", "crew_code", "production_rate")
        }
        if operational["activity"] and (operational["crew_code"] or operational["production_rate"]):
            eligible_sheets.add(sheet)
            normalized_mappings[str(sheet)] = operational

    canonical_rows = canonicalize_export_rows(session.get("audit_sheets", {}), mappings)
    evidence_rows = [
        {
            "sheet": str(row.get("__sheet", "")),
            "source_row": str(row.get("__source_row", "")),
            "activity": str(row.get("activity", "") or ""),
            "crew_code": str(row.get("crew_code", "") or ""),
            "production_rate": str(row.get("production_rate", "") or ""),
        }
        for row in canonical_rows
        if row.get("__sheet") in eligible_sheets
    ]
    payload = json.dumps(
        {"mappings": normalized_mappings, "rows": evidence_rows},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _clear_stale_operational_evidence(session: dict[str, Any]) -> bool:
    if not session.get("operational_reference_results"):
        return False
    expected = str(session.get("operational_source_fingerprint", "") or "")
    current = operational_source_fingerprint(session)
    if expected and expected == current:
        return False
    for key in _OPERATIONAL_SESSION_KEYS:
        session.pop(key, None)
    return True


def install_operational_reference_ui() -> None:
    """Install atomic operational-upload routing and source-drift invalidation."""
    if getattr(_server, "_operational_reference_ui_installed", False):
        return

    original_validate = _reference_session.validate_reference_submission
    original_operational_panel = _reference_session._operational_panel

    def validate_reference_submission(session, uploads, revisions=None):
        revisions = revisions or {}
        regular_uploads = {key: uploads[key] for key in _REGULAR_UPLOAD_KEYS if key in uploads}
        operational_upload = uploads.get("operational_reference")
        if not regular_uploads and operational_upload is None:
            raise _server.InputError(
                "Choose at least one Activity or Resource reference CSV, or an Operational Activity reference CSV."
            )

        pending: dict[str, Any] = {}
        if regular_uploads:
            pending.update(original_validate(session, regular_uploads, revisions))
        if operational_upload is not None:
            pending.update(
                _reference_session.validate_operational_submission(
                    session,
                    operational_upload,
                    revisions.get("operational_activity", ""),
                )
            )
            pending["operational_source_fingerprint"] = operational_source_fingerprint(session)
        return pending

    def operational_panel(token, session):
        stale_cleared = _clear_stale_operational_evidence(session)
        rendered = original_operational_panel(token, session)
        if stale_cleared and rendered:
            notice = (
                "<div class='notice'><strong>Previous operational evidence was cleared.</strong> "
                "The included source rows or explicit Activity/Crew/Production mapping changed, so the prior comparison is no longer current. Supply the governed operational reference again if needed.</div>"
            )
            rendered = rendered.replace("<h2>Operational Activity evidence</h2>", "<h2>Operational Activity evidence</h2>" + notice, 1)
        return rendered

    _reference_session.validate_reference_submission = validate_reference_submission
    _reference_session._operational_panel = operational_panel
    _server._operational_reference_ui_installed = True
