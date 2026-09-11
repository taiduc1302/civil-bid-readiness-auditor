from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from artifact_plan import artifact_plan_digest, plan_versioned_test_artifact, validate_artifact_plan
from output_gate import build_output_manifest, output_manifest_digest, validate_output_manifest
from prewrite_verification import sha256_bytes, verify_prewrite_inputs


BIDITEM_BYTES = b"synthetic project biditem authority"
BASELINE_BYTES = b"synthetic activities baseline"
SCHEMA_BYTES = b"synthetic approved schema"


def sources():
    return [
        {
            "role": "project_biditem_authority",
            "filename": "Project_Biditems.xlsx",
            "revision": "R1",
            "sha256": sha256_bytes(BIDITEM_BYTES),
            "authority_status": "APPROVED",
        },
        {
            "role": "baseline_activities_import",
            "filename": "Activities_Import_Baseline.xlsx",
            "revision": "B1",
            "sha256": sha256_bytes(BASELINE_BYTES),
            "authority_status": "APPROVED",
        },
    ]


def approvals():
    return {
        "estimator_setup_approved": True,
        "estimator_quantity_approved": True,
        "commercial_approved": True,
    }


def schema():
    return {
        "filename": "Activities_Import_Template.xlsx",
        "revision": "schema-1",
        "sha256": sha256_bytes(SCHEMA_BYTES),
        "authority_status": "APPROVED",
    }


def gate():
    return build_output_manifest(sources(), approvals(), [], "v1")


def plan(gate_manifest=None):
    return plan_versioned_test_artifact(
        gate_manifest or gate(),
        "controlled/Activities_Import_Baseline.xlsx",
        "controlled/Activities_Import_TEST-v2.xlsx",
        "v2",
        schema(),
    )


class OutputPipelineBindingTests(unittest.TestCase):
    def test_gate_manifest_digest_is_deterministic_and_validated(self):
        first = gate()
        second = gate()
        self.assertEqual(first, second)
        self.assertEqual(first["gate_manifest_sha256"], output_manifest_digest(first))
        self.assertIs(validate_output_manifest(first), first)

    def test_forged_ready_boolean_cannot_override_missing_approval(self):
        forged = gate()
        forged["approvals"]["commercial_approved"] = False
        forged["eligible_for_controlled_test_artifact_preparation"] = True
        forged["blockers"] = []
        forged["gate_manifest_sha256"] = output_manifest_digest(forged)
        with self.assertRaisesRegex(ValueError, "semantic state"):
            validate_output_manifest(forged)
        result = plan(forged)
        self.assertFalse(result["ready_for_candidate_writer"])
        self.assertTrue(any("output gate manifest validation failed" in item for item in result["blockers"]))

    def test_forged_ready_boolean_cannot_override_missing_required_source(self):
        forged = gate()
        forged["source_register"] = [item for item in forged["source_register"] if item["role"] != "project_biditem_authority"]
        forged["eligible_for_controlled_test_artifact_preparation"] = True
        forged["blockers"] = []
        forged["gate_manifest_sha256"] = output_manifest_digest(forged)
        result = plan(forged)
        self.assertFalse(result["ready_for_candidate_writer"])
        self.assertTrue(any("output gate manifest validation failed" in item for item in result["blockers"]))

    def test_gate_digest_tampering_is_rejected(self):
        forged = gate()
        forged["gate_manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_output_manifest(forged)

    def test_plan_is_bound_to_exact_gate_manifest(self):
        gate_manifest = gate()
        artifact_plan = plan(gate_manifest)
        self.assertTrue(artifact_plan["ready_for_candidate_writer"])
        self.assertEqual(artifact_plan["gate_manifest_sha256"], gate_manifest["gate_manifest_sha256"])
        self.assertEqual(artifact_plan["artifact_plan_sha256"], artifact_plan_digest(artifact_plan))
        self.assertIs(validate_artifact_plan(artifact_plan, gate_manifest), artifact_plan)

    def test_mutated_plan_cannot_be_resealed_by_changing_only_digest(self):
        gate_manifest = gate()
        forged = deepcopy(plan(gate_manifest))
        forged["output_path"] = "controlled/Other_TEST-v2.xlsx"
        forged["artifact_plan_sha256"] = artifact_plan_digest(forged)
        with self.assertRaisesRegex(ValueError, "semantic state"):
            validate_artifact_plan(forged, gate_manifest)

    def test_plan_from_different_gate_is_rejected(self):
        first_gate = gate()
        second_sources = sources()
        second_sources[0] = {**second_sources[0], "revision": "R2"}
        second_gate = build_output_manifest(second_sources, approvals(), [], "v1")
        artifact_plan = plan(first_gate)
        with self.assertRaises(ValueError):
            validate_artifact_plan(artifact_plan, second_gate)

    def test_prewrite_rejects_forged_gate_even_when_source_bytes_match(self):
        forged_gate = gate()
        forged_gate["approvals"]["commercial_approved"] = False
        forged_gate["eligible_for_controlled_test_artifact_preparation"] = True
        forged_gate["blockers"] = []
        forged_gate["gate_manifest_sha256"] = output_manifest_digest(forged_gate)
        forged_plan = plan(forged_gate)
        forged_plan["ready_for_candidate_writer"] = True
        forged_plan["blockers"] = []
        forged_plan["artifact_plan_sha256"] = artifact_plan_digest(forged_plan)
        result = verify_prewrite_inputs(
            forged_gate,
            forged_plan,
            {
                "project_biditem_authority": BIDITEM_BYTES,
                "baseline_activities_import": BASELINE_BYTES,
            },
            SCHEMA_BYTES,
        )
        self.assertFalse(result["verified_for_candidate_write"])
        self.assertTrue(any("output gate manifest validation failed at pre-write" in item for item in result["blockers"]))
        self.assertFalse(result["control_flags"]["HEAVYBID_IMPORT_VALIDATED"])

    def test_prewrite_happy_path_remains_review_only(self):
        gate_manifest = gate()
        artifact_plan = plan(gate_manifest)
        result = verify_prewrite_inputs(
            gate_manifest,
            artifact_plan,
            {
                "project_biditem_authority": BIDITEM_BYTES,
                "baseline_activities_import": BASELINE_BYTES,
            },
            SCHEMA_BYTES,
        )
        self.assertTrue(result["verified_for_candidate_write"])
        self.assertFalse(result["write_performed"])
        self.assertFalse(result["control_flags"]["HEAVYBID_IMPORT_VALIDATED"])


if __name__ == "__main__":
    unittest.main()
