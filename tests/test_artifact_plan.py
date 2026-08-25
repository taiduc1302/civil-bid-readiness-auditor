from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from artifact_plan import plan_versioned_test_artifact
from output_gate import build_output_manifest


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def gate_manifest():
    sources = [
        {"role": "project_biditem_authority", "filename": "Project_Biditems.xlsx", "revision": "R1", "sha256": HASH_A, "authority_status": "APPROVED"},
        {"role": "baseline_activities_import", "filename": "Activities_Import_Baseline.xlsx", "revision": "B1", "sha256": HASH_B, "authority_status": "APPROVED"},
    ]
    approvals = {"estimator_setup_approved": True, "estimator_quantity_approved": True, "commercial_approved": True}
    return build_output_manifest(sources, approvals, [], "v1")


def schema_authority():
    return {"filename": "Activities_Import_Template.xlsx", "revision": "schema-1", "sha256": HASH_C, "authority_status": "APPROVED"}


class ArtifactPlanTests(unittest.TestCase):
    def test_valid_plan_is_create_new_only_and_still_not_import_validated(self):
        result = plan_versioned_test_artifact(
            gate_manifest(),
            "controlled/Activities_Import_Baseline.xlsx",
            "controlled/Activities_Import_TEST-v2.xlsx",
            "v2",
            schema_authority(),
        )
        self.assertTrue(result["ready_for_candidate_writer"])
        self.assertEqual(result["write_mode"], "CREATE_NEW_ONLY")
        self.assertFalse(result["overwrite_allowed"])
        self.assertFalse(result["artifact_created"])
        self.assertFalse(result["heavybid_import_attempted"])
        self.assertFalse(result["control_flags"]["HEAVYBID_IMPORT_VALIDATED"])

    def test_same_path_is_blocked_case_insensitively(self):
        result = plan_versioned_test_artifact(
            gate_manifest(),
            "Controlled/Activities.xlsx",
            "controlled\\activities.xlsx",
            "v1",
            schema_authority(),
        )
        self.assertFalse(result["ready_for_candidate_writer"])
        self.assertIn("output_path must not overwrite baseline_path", result["blockers"])

    def test_output_must_be_versioned_xlsx(self):
        bad_extension = plan_versioned_test_artifact(gate_manifest(), "base.xlsx", "candidate-v2.csv", "v2", schema_authority())
        self.assertIn("candidate output_path must use .xlsx", bad_extension["blockers"])
        missing_version = plan_versioned_test_artifact(gate_manifest(), "base.xlsx", "candidate.xlsx", "v2", schema_authority())
        self.assertIn("output_path filename must contain output_version", missing_version["blockers"])

    def test_invalid_or_unapproved_schema_blocks_plan(self):
        schema = {"filename": "Template.xlsx", "revision": "R1", "sha256": "bad", "authority_status": "REFERENCE_ONLY"}
        result = plan_versioned_test_artifact(gate_manifest(), "base.xlsx", "candidate-v2.xlsx", "v2", schema)
        self.assertFalse(result["ready_for_candidate_writer"])
        self.assertIn("schema authority sha256 is invalid", result["blockers"])
        self.assertIn("schema authority must be APPROVED", result["blockers"])

    def test_failed_gate_cannot_be_bypassed(self):
        manifest = gate_manifest()
        manifest["eligible_for_controlled_test_artifact_preparation"] = False
        result = plan_versioned_test_artifact(manifest, "base.xlsx", "candidate-v2.xlsx", "v2", schema_authority())
        self.assertFalse(result["ready_for_candidate_writer"])
        self.assertIn("output eligibility gate has not passed", result["blockers"])

    def test_control_flags_cannot_be_relaxed(self):
        manifest = gate_manifest()
        manifest["control_flags"] = {"NOT_PRODUCTION_READY": False, "NOT_ESTIMATOR_VALIDATED": False, "HEAVYBID_IMPORT_VALIDATED": True}
        result = plan_versioned_test_artifact(manifest, "base.xlsx", "candidate-v2.xlsx", "v2", schema_authority())
        self.assertFalse(result["ready_for_candidate_writer"])
        self.assertIn("NOT_PRODUCTION_READY must remain true", result["blockers"])
        self.assertIn("NOT_ESTIMATOR_VALIDATED must remain true", result["blockers"])
        self.assertIn("HEAVYBID_IMPORT_VALIDATED must remain false", result["blockers"])

    def test_baseline_source_identity_is_carried_from_gate_manifest(self):
        result = plan_versioned_test_artifact(gate_manifest(), "base.xlsx", "candidate-v2.xlsx", "v2", schema_authority())
        self.assertEqual(result["baseline_source"]["filename"], "Activities_Import_Baseline.xlsx")
        self.assertEqual(result["baseline_source"]["sha256"], HASH_B)


if __name__ == "__main__":
    unittest.main()
