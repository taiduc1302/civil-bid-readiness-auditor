"""Pure planning contract for future bulk human finding dispositions.

This module deliberately does not apply review-state changes. It validates an
explicit selection against the current deterministic finding set and records
the expected current human states so a future apply step can fail closed on a
stale session.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from finding_review import validate_disposition

PLAN_FORMAT = "civil-estimate-bulk-review-plan"
PLAN_VERSION = 1


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


def build_bulk_review_plan(
    result: dict[str, Any],
    dispositions: dict[int, dict[str, str]],
    finding_ids: Iterable[Any],
    target_status: str,
    reason: str = "",
    *,
    ownership_acknowledged: bool = False,
) -> dict[str, Any]:
    """Validate and return a non-applying bulk review plan.

    The caller must explicitly acknowledge human ownership. The plan records
    expected current states and a deterministic finding-set fingerprint, but
    never mutates findings or dispositions and cannot apply itself.
    """
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
            {
                "id": finding_id,
                "status": current_status,
                "reason": current_reason,
            }
        )

    target_identities = [_finding_identity(findings[finding_id]) for finding_id in selected_ids]
    return {
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
