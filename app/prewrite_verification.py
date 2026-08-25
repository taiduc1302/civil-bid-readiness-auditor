"""Revalidate reviewed source identities immediately before any future candidate write.

This module hashes in-memory bytes supplied by the caller. It does not read or
write project files by itself and never creates a HeavyBid artifact.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_prewrite_inputs(
    gate_manifest: dict[str, Any],
    artifact_plan: dict[str, Any],
    source_bytes_by_role: dict[str, bytes],
    schema_bytes: bytes | None,
) -> dict[str, Any]:
    """Fail closed if reviewed evidence differs from the bytes presented to a writer."""
    blockers: list[str] = []
    checks: list[dict[str, str]] = []

    if artifact_plan.get("ready_for_candidate_writer") is not True:
        blockers.append("artifact plan is not ready for candidate writer")

    flags = artifact_plan.get("control_flags", {})
    if flags.get("NOT_PRODUCTION_READY") is not True:
        blockers.append("NOT_PRODUCTION_READY must remain true")
    if flags.get("NOT_ESTIMATOR_VALIDATED") is not True:
        blockers.append("NOT_ESTIMATOR_VALIDATED must remain true")
    if flags.get("HEAVYBID_IMPORT_VALIDATED") is not False:
        blockers.append("HEAVYBID_IMPORT_VALIDATED must remain false")

    sources = list(gate_manifest.get("source_register", []))
    role_counts = Counter(str(source.get("role", "")).strip() for source in sources if str(source.get("role", "")).strip())
    for role, count in sorted(role_counts.items()):
        if count > 1:
            blockers.append(f"ambiguous duplicate source role at pre-write: {role}")

    for source in sources:
        role = str(source.get("role", "")).strip()
        expected = str(source.get("sha256", "")).strip().lower()
        filename = str(source.get("filename", "")).strip()
        if not role:
            blockers.append("source register entry is missing role at pre-write")
            continue
        current = source_bytes_by_role.get(role)
        if current is None:
            blockers.append(f"missing current bytes for source role: {role}")
            checks.append({"role": role, "filename": filename, "expected_sha256": expected, "actual_sha256": "", "status": "MISSING"})
            continue
        actual = sha256_bytes(current)
        status = "MATCH" if actual == expected else "CHANGED"
        checks.append({"role": role, "filename": filename, "expected_sha256": expected, "actual_sha256": actual, "status": status})
        if status != "MATCH":
            blockers.append(f"source changed since review: {role}")

    plan_baseline = artifact_plan.get("baseline_source") or {}
    manifest_baseline = next((source for source in sources if source.get("role") == "baseline_activities_import"), None)
    if manifest_baseline is None:
        blockers.append("gate manifest is missing baseline_activities_import at pre-write")
    elif any(
        str(plan_baseline.get(field, "")).strip().lower() != str(manifest_baseline.get(field, "")).strip().lower()
        for field in ("filename", "revision", "sha256", "authority_status")
    ):
        blockers.append("baseline identity drift between artifact plan and gate manifest")

    schema = artifact_plan.get("schema_authority") or {}
    expected_schema_sha = str(schema.get("sha256", "")).strip().lower()
    if schema_bytes is None:
        blockers.append("missing current schema bytes at pre-write")
        schema_check = {"filename": str(schema.get("filename", "")), "expected_sha256": expected_schema_sha, "actual_sha256": "", "status": "MISSING"}
    else:
        actual_schema_sha = sha256_bytes(schema_bytes)
        schema_status = "MATCH" if actual_schema_sha == expected_schema_sha else "CHANGED"
        schema_check = {"filename": str(schema.get("filename", "")), "expected_sha256": expected_schema_sha, "actual_sha256": actual_schema_sha, "status": schema_status}
        if schema_status != "MATCH":
            blockers.append("schema authority changed since planning")

    return {
        "verified_for_candidate_write": not blockers,
        "blockers": blockers,
        "source_checks": checks,
        "schema_check": schema_check,
        "write_performed": False,
        "control_flags": {
            "NOT_PRODUCTION_READY": True,
            "NOT_ESTIMATOR_VALIDATED": True,
            "HEAVYBID_IMPORT_VALIDATED": False,
        },
    }
