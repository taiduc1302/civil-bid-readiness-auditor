"""Plan a versioned candidate test artifact without writing any file.

This module enforces no-overwrite and identity controls after the output eligibility
gate passes. It still does not create a workbook or claim HeavyBid import validity.
"""
from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm_path(value: str) -> str:
    return value.replace("\\", "/").strip().casefold()


def plan_versioned_test_artifact(
    gate_manifest: dict[str, Any],
    baseline_path: str,
    output_path: str,
    output_version: str,
    schema_authority: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic candidate-writer plan; never writes or overwrites files."""
    blockers: list[str] = []

    if gate_manifest.get("eligible_for_controlled_test_artifact_preparation") is not True:
        blockers.append("output eligibility gate has not passed")

    flags = gate_manifest.get("control_flags", {})
    if flags.get("NOT_PRODUCTION_READY") is not True:
        blockers.append("NOT_PRODUCTION_READY must remain true")
    if flags.get("NOT_ESTIMATOR_VALIDATED") is not True:
        blockers.append("NOT_ESTIMATOR_VALIDATED must remain true")
    if flags.get("HEAVYBID_IMPORT_VALIDATED") is not False:
        blockers.append("HEAVYBID_IMPORT_VALIDATED must remain false")

    baseline = _text(baseline_path)
    output = _text(output_path)
    version = _text(output_version)
    if not baseline:
        blockers.append("baseline_path is required")
    if not output:
        blockers.append("output_path is required")
    if baseline and output and _norm_path(baseline) == _norm_path(output):
        blockers.append("output_path must not overwrite baseline_path")
    if output and PurePath(output).suffix.casefold() != ".xlsx":
        blockers.append("candidate output_path must use .xlsx")
    if not version or not _VERSION_RE.fullmatch(version):
        blockers.append("output_version must use only letters, numbers, dot, underscore, or hyphen")
    elif output and version.casefold() not in PurePath(output).stem.casefold():
        blockers.append("output_path filename must contain output_version")

    schema_filename = _text(schema_authority.get("filename"))
    schema_revision = _text(schema_authority.get("revision"))
    schema_sha256 = _text(schema_authority.get("sha256"))
    schema_status = _text(schema_authority.get("authority_status"))
    if not schema_filename:
        blockers.append("schema authority filename is required")
    if not schema_revision:
        blockers.append("schema authority revision is required")
    if not _SHA256_RE.fullmatch(schema_sha256):
        blockers.append("schema authority sha256 is invalid")
    if schema_status != "APPROVED":
        blockers.append("schema authority must be APPROVED")

    baseline_source = next(
        (
            item
            for item in gate_manifest.get("source_register", [])
            if item.get("role") == "baseline_activities_import"
        ),
        None,
    )
    if baseline_source is None:
        blockers.append("gate manifest is missing baseline_activities_import source identity")

    return {
        "ready_for_candidate_writer": not blockers,
        "blockers": blockers,
        "write_mode": "CREATE_NEW_ONLY",
        "overwrite_allowed": False,
        "baseline_path": baseline,
        "baseline_source": baseline_source,
        "output_path": output,
        "output_version": version,
        "schema_authority": {
            "filename": schema_filename,
            "revision": schema_revision,
            "sha256": schema_sha256.lower(),
            "authority_status": schema_status,
        },
        "artifact_created": False,
        "heavybid_import_attempted": False,
        "control_flags": {
            "NOT_PRODUCTION_READY": True,
            "NOT_ESTIMATOR_VALIDATED": True,
            "HEAVYBID_IMPORT_VALIDATED": False,
        },
    }
