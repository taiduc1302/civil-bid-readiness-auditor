"""Deterministic eligibility gate for future controlled HeavyBid-readable test artifacts.

This module does not create or import HeavyBid files. It evaluates whether the
minimum governed evidence and approvals are present before a separate controlled
output-preparation step could even be considered.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


REQUIRED_SOURCE_ROLES = (
    "project_biditem_authority",
    "baseline_activities_import",
)
REQUIRED_APPROVALS = (
    "estimator_setup_approved",
    "estimator_quantity_approved",
    "commercial_approved",
)
RESOLVED_EXCEPTION_STATUSES = ("RESOLVED", "APPROVED_EXCEPTION")
CONTROL_FLAGS = {
    "NOT_PRODUCTION_READY": True,
    "NOT_ESTIMATOR_VALIDATED": True,
    "HEAVYBID_IMPORT_VALIDATED": False,
}
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _validate_source_register(sources: Iterable[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    normalized: list[dict[str, str]] = []
    blockers: list[str] = []
    roles: list[str] = []

    for index, source in enumerate(sources, start=1):
        role = _clean(source.get("role"))
        filename = _clean(source.get("filename"))
        revision = _clean(source.get("revision"))
        sha256 = _clean(source.get("sha256"))
        authority_status = _clean(source.get("authority_status"))
        if not role:
            blockers.append(f"source[{index}] is missing role")
        if not filename:
            blockers.append(f"source[{index}] is missing filename")
        if not revision:
            blockers.append(f"source[{index}] is missing revision")
        if not _SHA256_RE.fullmatch(sha256):
            blockers.append(f"source[{index}] has invalid sha256")
        if authority_status not in {"APPROVED", "REFERENCE_ONLY"}:
            blockers.append(f"source[{index}] has unsupported authority_status")
        normalized.append({
            "role": role,
            "filename": filename,
            "revision": revision,
            "sha256": sha256.lower(),
            "authority_status": authority_status,
        })
        if role:
            roles.append(role)

    counts = Counter(roles)
    for role in REQUIRED_SOURCE_ROLES:
        if counts[role] == 0:
            blockers.append(f"missing required source role: {role}")
        elif counts[role] > 1:
            blockers.append(f"ambiguous duplicate required source role: {role}")
        else:
            source = next(item for item in normalized if item["role"] == role)
            if source["authority_status"] != "APPROVED":
                blockers.append(f"required source role is not APPROVED: {role}")

    return normalized, blockers


def _validate_approvals(approvals: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for approval in REQUIRED_APPROVALS:
        if approvals.get(approval) is not True:
            blockers.append(f"missing required approval: {approval}")
    return blockers


def _validate_exceptions(exceptions: Iterable[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    normalized: list[dict[str, str]] = []
    blockers: list[str] = []
    for index, exception in enumerate(exceptions, start=1):
        exception_id = _clean(exception.get("id")) or f"exception-{index}"
        status = _clean(exception.get("status")).upper()
        reason = _clean(exception.get("reason"))
        normalized.append({"id": exception_id, "status": status, "reason": reason})
        if status not in RESOLVED_EXCEPTION_STATUSES:
            blockers.append(f"unresolved exception: {exception_id}")
        elif status == "APPROVED_EXCEPTION" and not reason:
            blockers.append(f"approved exception requires reason: {exception_id}")
    return normalized, blockers


def evaluate_output_eligibility(
    source_register: Iterable[dict[str, Any]],
    approvals: dict[str, Any],
    exceptions: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic gate result without creating any output artifact."""
    sources, source_blockers = _validate_source_register(source_register)
    exception_rows, exception_blockers = _validate_exceptions(exceptions)
    blockers = source_blockers + _validate_approvals(approvals) + exception_blockers
    return {
        "eligible_for_controlled_test_artifact_preparation": not blockers,
        "blockers": blockers,
        "source_register": sources,
        "approvals": {name: approvals.get(name) is True for name in REQUIRED_APPROVALS},
        "exceptions": exception_rows,
        "control_flags": dict(CONTROL_FLAGS),
    }


def build_output_manifest(
    source_register: Iterable[dict[str, Any]],
    approvals: dict[str, Any],
    exceptions: Iterable[dict[str, Any]],
    output_version: str,
) -> dict[str, Any]:
    """Build a review manifest only; this does not create a HeavyBid-readable file."""
    version = _clean(output_version)
    if not version:
        raise ValueError("output_version is required")
    result = evaluate_output_eligibility(source_register, approvals, exceptions)
    return {
        "manifest_version": "1",
        "output_version": version,
        **result,
        "artifact_created": False,
        "heavybid_import_attempted": False,
    }
