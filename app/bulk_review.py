"""Fail-closed planning and pure application for bulk human finding dispositions.

The module never mutates deterministic findings or governed reference data.
Bulk application returns a new dispositions mapping only after the current
finding identities and expected human states still match the approved plan.
No browser/session bulk control is wired here.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from finding_review import set_disposition, validate_disposition

PLAN_FORMAT = "civil-estimate-bulk-review-plan"
PLAN_VERSION = 2


def _finding_identity(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(finding["id"]),
        "severity": str(finding.get("severity", "")),
        "rule_id": str(finding.get("rule_id", "")),
        "sheet": str(finding.get("sheet", "")),
        "row": str(finding.get("row", "")),
        "field": str(finding.get("field", "")),
        "message": str(finding.get("message", "")),
    }


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def finding_set_fingerprint(result: dict[str, Any]) -> str:
    """Fingerprint the current deterministic finding identities in stable id order."""
    identities = [_finding_identity(item) for item in result.get("findings", [])]
    identities.sort(key=lambda item: item["id"])
    return _fingerprint(identities)


def _normalize_ids(finding_ids: Iterable[Any]) -> list[int]:
    if isinstance(finding_ids, (str, bytes)):
        raise ValueError("Bulk review targets must be an explicit collection of finding ids.")
    try:
        raw = list(finding_ids)
    except TypeError as exc:
        raise ValueError("Bulk review targets must be an explicit collection of finding ids.") from exc
    if not raw:
        raise ValueError("Bulk review requires at least one explicitly selected finding id.")

    normalized: list[int] = []
    for value in raw:
        if isinstance(value, bool):
            raise ValueError("Bulk review finding ids must be integers, not booleans.")
        try:
            finding_id = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid bulk review finding id: {value}") from exc
        if finding_id <= 0:
            raise ValueError(f"Invalid bulk review finding id: {finding_id}")
        normalized.append(finding_id)
    if len(normalized) != len(set(normalized)):
        raise ValueError("Bulk review selection contains duplicate finding ids.")
    return normalized


def _plan_digest(plan_without_digest: dict[str, Any]) -> str:
    return _fingerprint(plan_without_digest)


def build_bulk_review_plan(
    result: dict[str, Any],
    dispositions: dict[int, dict[str, str]],
    finding_ids: Iterable[Any],
    target_status: str,
    reason: str = "",
    *,
    ownership_acknowledged: bool = False,
) -> dict[str, Any]:
    """Validate and return an apply-ready but non-self-applying bulk review plan."""
    if ownership_acknowledged is not True:
        raise ValueError("Bulk review requires explicit human-ownership acknowledgement.")

    target_status, reason = validate_disposition(target_status, reason)
    selected_ids = _normalize_ids(finding_ids)

    findings = {int(item["id"]): item for item in result.get("findings", [])}
    if not findings:
        raise ValueError("Bulk review cannot target an audit result with no findings.")
    unknown = [finding_id for finding_id in selected_ids if finding_id not in findings]
    if unknown:
        raise ValueError("Unknown bulk review finding id(s): " + ", ".join(str(item) for item in unknown))

    expected_states: list[dict[str, Any]] = []
    for finding_id in selected_ids:
        state = dispositions.get(finding_id, {"status": "Open", "reason": ""})
        current_status, current_reason = validate_disposition(
            str(state.get("status", "Open")), str(state.get("reason", ""))
        )
        expected_states.append(
            {"id": finding_id, "status": current_status, "reason": current_reason}
        )

    target_identities = [_finding_identity(findings[finding_id]) for finding_id in selected_ids]
    plan: dict[str, Any] = {
        "plan_format": PLAN_FORMAT,
        "plan_version": PLAN_VERSION,
        "target_ids": selected_ids,
        "target_count": len(selected_ids),
        "target_status": target_status,
        "reason": reason,
        "ownership_acknowledged": True,
        "finding_set_sha256": finding_set_fingerprint(result),
        "target_findings_sha256": _fingerprint(target_identities),
        "expected_current_states": expected_states,
        "apply_automatically": False,
        "mutates_deterministic_findings": False,
        "mutates_reference_results": False,
        "changes_score": False,
    }
    plan["plan_sha256"] = _plan_digest(plan)
    return plan


def _validate_plan_digest(plan: dict[str, Any]) -> None:
    digest = str(plan.get("plan_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Bulk review plan SHA-256 is missing or invalid.")
    core = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if _plan_digest(core) != digest:
        raise ValueError("Bulk review plan SHA-256 does not match plan contents.")


def _expected_states(plan: dict[str, Any], target_ids: list[int]) -> list[dict[str, Any]]:
    raw = plan.get("expected_current_states")
    if not isinstance(raw, list) or len(raw) != len(target_ids):
        raise ValueError("Bulk review plan expected-current-state list is invalid.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError("Bulk review plan expected-current-state entry is invalid.")
        try:
            finding_id = int(item.get("id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Bulk review plan expected-current-state id is invalid.") from exc
        if finding_id != target_ids[index]:
            raise ValueError("Bulk review plan expected-current-state ids do not match target ids.")
        status, reason = validate_disposition(
            str(item.get("status", "")), str(item.get("reason", ""))
        )
        normalized.append({"id": finding_id, "status": status, "reason": reason})
    return normalized


def apply_bulk_review_plan(
    result: dict[str, Any],
    dispositions: dict[int, dict[str, str]],
    plan: dict[str, Any],
) -> dict[int, dict[str, str]]:
    """Return a new dispositions map only when the approved plan is still current.

    This is intentionally pure with respect to the supplied mappings. It is not
    connected to browser/session mutation; a caller would still need a separate
    explicit atomic assignment after this function succeeds.
    """
    if not isinstance(plan, dict):
        raise ValueError("Bulk review plan must be a mapping.")
    if plan.get("plan_format") != PLAN_FORMAT or plan.get("plan_version") != PLAN_VERSION:
        raise ValueError("Bulk review plan format/version is unsupported.")
    _validate_plan_digest(plan)

    if plan.get("ownership_acknowledged") is not True:
        raise ValueError("Bulk review plan lacks explicit human-ownership acknowledgement.")
    if plan.get("apply_automatically") is not False:
        raise ValueError("Bulk review plan cannot enable automatic application.")
    for flag in ("mutates_deterministic_findings", "mutates_reference_results", "changes_score"):
        if plan.get(flag) is not False:
            raise ValueError(f"Bulk review plan contains a relaxed safety flag: {flag}")

    target_ids = _normalize_ids(plan.get("target_ids", []))
    target_count = plan.get("target_count")
    if isinstance(target_count, bool) or not isinstance(target_count, int) or target_count != len(target_ids):
        raise ValueError("Bulk review plan target count does not match target ids.")
    target_status, reason = validate_disposition(
        str(plan.get("target_status", "")), str(plan.get("reason", ""))
    )

    findings = {int(item["id"]): item for item in result.get("findings", [])}
    if not findings:
        raise ValueError("Bulk review cannot apply to an audit result with no findings.")
    unknown = [finding_id for finding_id in target_ids if finding_id not in findings]
    if unknown:
        raise ValueError("Bulk review plan targets unknown finding id(s): " + ", ".join(str(item) for item in unknown))

    if str(plan.get("finding_set_sha256", "")) != finding_set_fingerprint(result):
        raise ValueError("Bulk review plan is stale: deterministic finding set changed.")
    target_identities = [_finding_identity(findings[finding_id]) for finding_id in target_ids]
    if str(plan.get("target_findings_sha256", "")) != _fingerprint(target_identities):
        raise ValueError("Bulk review plan is stale: selected finding identity changed.")

    expected = _expected_states(plan, target_ids)
    for expected_state in expected:
        finding_id = expected_state["id"]
        current = dispositions.get(finding_id, {"status": "Open", "reason": ""})
        current_status, current_reason = validate_disposition(
            str(current.get("status", "Open")), str(current.get("reason", ""))
        )
        if current_status != expected_state["status"] or current_reason != expected_state["reason"]:
            raise ValueError(f"Bulk review plan is stale: current review state changed for finding {finding_id}.")

    pending = {int(key): dict(value) for key, value in dispositions.items()}
    for finding_id in target_ids:
        pending.setdefault(finding_id, {"status": "Open", "reason": ""})
        set_disposition(pending, finding_id, target_status, reason)
    return pending
