from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from artifact_plan import plan_versioned_test_artifact
from output_gate import build_output_manifest
from prewrite_verification import sha256_bytes, verify_prewrite_inputs


BIDITEM_BYTES = b"synthetic project biditem authority"
BASELINE_BYTES = b"synthetic activities baseline"
SCHEMA_BYTES = b"synthetic approved schema"


def gate_manifest():
    sources = [
        {"role": "project_biditem_authority", "filename": "Project_Biditems.xlsx", "revision": "R1", "sha256": sha256_bytes(BIDITEM_BYTES), "authority_status": "APPROVED"},
        {"role": "baseline_activities_import", "filename": "Activities_Import_Baseline.xlsx", "revision": "B1", "sha256": sha256_bytes(BASELINE_BYTES), "authority_status": "APPROVED"},
    ]
    approvals = {"estimator_setup_approved": True, "estimator_quantity_approved": True, "commercial_approved": True}
    return build_output_manifest(sources, approvals, [], "v1")


def artifact_plan():
    return plan_versioned_test_artifact(
        gate_manifest(),
        "controlled/Activities_Import_Baseline.xlsx",
        "controlled/Activities_Import_TEST-v2.xlsx",
        "v2",
        {"filename": "Activities_Import_Template.xlsx", "revision": "schema-1", "sha256": sha256_bytes(SCHEMA_BYTES), "authority_status": "APPROVED"},
    )


class PrewriteVerificationTests(unittest.TestCase):
    def current_sources(self):
        return {"project_biditem_authority": BIDITEM_BYTES, "baseline_activities_import": BASELINE_BYTES}

    def test_all_current_bytes_match_reviewed_hashes(self):
        result = verify_prewrite_inputs(gate_manifest(), artifact_plan(), self.current_sources(), SCHEMA_BYTES)
        self.assertTrue(result["verified_for_candidate_write"])
        self.assertEqual(result["blockers"], [])
        self.assertTrue(all(check["status"] == "MATCH" for check in result["source_checks"]))
        self.assertEqual(result["schema_check"]["status"], "MATCH")
        self.assertFalse(result["write_performed"])
        self.assertFalse(result["control_flags"]["HEAVYBID_IMPORT_VALIDATED"])

    def test_changed_source_blocks_candidate_write(self):
        current = self.current_sources()
        current["baseline_activities_import"] = b"changed baseline"
        result = verify_prewrite_inputs(gate_manifest(), artifact_plan(), current, SCHEMA_BYTES)
        self.assertFalse(result["verified_for_candidate_write"])
        self.assertIn("source changed since review: baseline_activities_import", result["blockers"])
        changed = next(check for check in result["source_checks"] if check["role"] == "baseline_activities_import")
        self.assertEqual(changed["status"], "CHANGED")

    def test_missing_source_bytes_block_candidate_write(self):
        current = {"project_biditem_authority": BIDITEM_BYTES}
        result = verify_prewrite_inputs(gate_manifest(), artifact_plan(), current, SCHEMA_BYTES)
        self.assertFalse(result["verified_for_candidate_write"])
        self.assertIn("missing current bytes for source role: baseline_activities_import", result["blockers"])

    def test_changed_or_missing_schema_blocks_candidate_write(self):
        changed = verify_prewrite_inputs(gate_manifest(), artifact_plan(), self.current_sources(), b"changed schema")
        self.assertIn("schema authority changed since planning", changed["blockers"])
        missing = verify_prewrite_inputs(gate_manifest(), artifact_plan(), self.current_sources(), None)
        self.assertIn("missing current schema bytes at pre-write", missing["blockers"])

    def test_baseline_identity_drift_between_plan_and_gate_is_blocked(self):
        plan = artifact_plan()
        plan["baseline_source"] = {**plan["baseline_source"], "revision": "DIFFERENT"}
        result = verify_prewrite_inputs(gate_manifest(), plan, self.current_sources(), SCHEMA_BYTES)
        self.assertFalse(result["verified_for_candidate_write"])
        self.assertIn("baseline identity drift between artifact plan and gate manifest", result["blockers"])

    def test_nonready_plan_cannot_be_bypassed(self):
        plan = artifact_plan()
        plan["ready_for_candidate_writer"] = False
        result = verify_prewrite_inputs(gate_manifest(), plan, self.current_sources(), SCHEMA_BYTES)
        self.assertIn("artifact plan is not ready for candidate writer", result["blockers"])

    def test_relaxed_control_flags_are_blocked(self):
        plan = artifact_plan()
        plan["control_flags"] = {"NOT_PRODUCTION_READY": False, "NOT_ESTIMATOR_VALIDATED": False, "HEAVYBID_IMPORT_VALIDATED": True}
        result = verify_prewrite_inputs(gate_manifest(), plan, self.current_sources(), SCHEMA_BYTES)
        self.assertFalse(result["verified_for_candidate_write"])
        self.assertIn("NOT_PRODUCTION_READY must remain true", result["blockers"])
        self.assertIn("NOT_ESTIMATOR_VALIDATED must remain true", result["blockers"])
        self.assertIn("HEAVYBID_IMPORT_VALIDATED must remain false", result["blockers"])


if __name__ == "__main__":
    unittest.main()
