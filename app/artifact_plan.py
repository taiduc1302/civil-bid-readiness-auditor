"""Plan a versioned candidate test artifact without writing any file.

This module enforces no-overwrite and identity controls after the output eligibility
gate passes. It still does not create a workbook or claim HeavyBid import validity.
"""
from __future__ import annotations

import hashlib
import json
import ntpath
import re
from copy import deepcopy
from pathlib import PureWindowsPath
from typing import Any

from output_gate import validate_output_manifest


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm_path(value: str) -> str:
    """Return deterministic lexical Windows-path identity without touching disk."""
    text = value.strip().replace("/", "\\")
    return ntpath.normcase(ntpath.normpath(text))


def _canonical_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def artifact_plan_digest(plan: dict[str, Any]) -> str:
    """Return the deterministic digest over a plan excluding its digest field."""
    body = deepcopy(plan)
    body.pop("artifact_plan_sha256", None)
    return _canonical_digest(body)


def plan_versioned_test_artifact(
    gate_manifest: dict[str, Any],
    baseline_path: str,
    output_path: str,
    output_version: str,
    schema_authority: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic candidate-writer plan; never writes or overwrites files."""
    blockers: list[str] = []

    gate_valid = True
    try:
        validate_output_manifest(gate_manifest)
    except (TypeError, ValueError) as exc:
        gate_valid = False
        blockers.append(f"output gate manifest validation failed: {exc}")

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
    output_name = PureWindowsPath(output)
    if output and output_name.suffix.casefold() != ".xlsx":
        blockers.append("candidate output_path must use .xlsx")
    if not version or not _VERSION_RE.fullmatch(version):
        blockers.append("output_version must use only letters, numbers, dot, underscore, or hyphen")
    elif output and version.casefold() not in output_name.stem.casefold():
        blockers.append("output_path filename must contain output_version")

    if not isinstance(schema_authority, dict):
        schema_authority = {}
        blockers.append("schema authority is malformed")
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

    source_register = gate_manifest.get("source_register", [])
    if not isinstance(source_register, list):
        source_register = []
    baseline_source = next(
        (
            item
            for item in source_register
            if isinstance(item, dict) and item.get("role") == "baseline_activities_import"
        ),
        None,
    )
    if baseline_source is None:
        blockers.append("gate manifest is missing baseline_activities_import source identity")

    plan = {
        "ready_for_candidate_writer": not blockers,
        "blockers": blockers,
        "write_mode": "CREATE_NEW_ONLY",
        "overwrite_allowed": False,
        "filesystem_identity_recheck_required": True,
        "exclusive_create_required": True,
        "gate_manifest_sha256": gate_manifest.get("gate_manifest_sha256", "") if gate_valid else "",
        "baseline_path": baseline,
        "baseline_path_lexical_identity": _norm_path(baseline) if baseline else "",
        "baseline_source": baseline_source,
        "output_path": output,
        "output_path_lexical_identity": _norm_path(output) if output else "",
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
    plan["artifact_plan_sha256"] = _canonical_digest(plan)
    return plan


def validate_artifact_plan(plan: dict[str, Any], gate_manifest: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless the plan exactly reproduces from the bound gate manifest."""
    validate_output_manifest(gate_manifest)
    if not isinstance(plan, dict):
        raise ValueError("artifact plan must be an object")
    schema = plan.get("schema_authority")
    if not isinstance(schema, dict):
        raise ValueError("artifact plan schema authority is malformed")
    expected = plan_versioned_test_artifact(
        gate_manifest,
        _text(plan.get("baseline_path")),
        _text(plan.get("output_path")),
        _text(plan.get("output_version")),
        schema,
    )
    if plan != expected:
        raise ValueError("artifact plan semantic state or digest does not match the bound gate manifest")
    if plan.get("gate_manifest_sha256") != gate_manifest.get("gate_manifest_sha256"):
        raise ValueError("artifact plan gate binding mismatch")
    if plan.get("artifact_plan_sha256") != artifact_plan_digest(plan):
        raise ValueError("artifact plan digest mismatch")
    if plan.get("filesystem_identity_recheck_required") is not True:
        raise ValueError("future writer filesystem identity recheck must remain required")
    if plan.get("exclusive_create_required") is not True:
        raise ValueError("future writer exclusive-create control must remain required")
    return plan
