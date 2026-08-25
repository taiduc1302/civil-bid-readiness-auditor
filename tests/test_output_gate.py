from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from output_gate import build_output_manifest, evaluate_output_eligibility


GOOD_HASH_A = "a" * 64
GOOD_HASH_B = "b" * 64


def approved_sources():
    return [
        {
            "role": "project_biditem_authority",
            "filename": "Project_Biditems.xlsx",
            "revision": "R1",
            "sha256": GOOD_HASH_A,
            "authority_status": "APPROVED",
        },
        {
            "role": "baseline_activities_import",
            "filename": "Activities_Import_Baseline.xlsx",
            "revision": "baseline-01",
            "sha256": GOOD_HASH_B,
            "authority_status": "APPROVED",
        },
    ]


def approvals():
    return {
        "estimator_setup_approved": True,
        "estimator_quantity_approved": True,
        "commercial_approved": True,
    }


class OutputGateTests(unittest.TestCase):
    def test_complete_governed_inputs_allow_preparation_but_never_validate_import(self):
        result = evaluate_output_eligibility(approved_sources(), approvals(), [])
        self.assertTrue(result["eligible_for_controlled_test_artifact_preparation"])
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["control_flags"]["NOT_PRODUCTION_READY"])
        self.assertTrue(result["control_flags"]["NOT_ESTIMATOR_VALIDATED"])
        self.assertFalse(result["control_flags"]["HEAVYBID_IMPORT_VALIDATED"])

    def test_missing_required_authority_blocks_gate(self):
        sources = approved_sources()[1:]
        result = evaluate_output_eligibility(sources, approvals(), [])
        self.assertFalse(result["eligible_for_controlled_test_artifact_preparation"])
        self.assertIn("missing required source role: project_biditem_authority", result["blockers"])

    def test_duplicate_required_authority_is_ambiguous_and_blocks_gate(self):
        sources = approved_sources() + [{**approved_sources()[0], "filename": "Other_Biditems.xlsx", "sha256": "c" * 64}]
        result = evaluate_output_eligibility(sources, approvals(), [])
        self.assertFalse(result["eligible_for_controlled_test_artifact_preparation"])
        self.assertIn("ambiguous duplicate required source role: project_biditem_authority", result["blockers"])

    def test_invalid_hash_and_reference_only_required_source_block_gate(self):
        sources = approved_sources()
        sources[0] = {**sources[0], "sha256": "not-a-hash", "authority_status": "REFERENCE_ONLY"}
        result = evaluate_output_eligibility(sources, approvals(), [])
        self.assertFalse(result["eligible_for_controlled_test_artifact_preparation"])
        self.assertTrue(any("invalid sha256" in blocker for blocker in result["blockers"]))
        self.assertIn("required source role is not APPROVED: project_biditem_authority", result["blockers"])

    def test_missing_any_required_approval_blocks_gate(self):
        values = approvals()
        values["commercial_approved"] = False
        result = evaluate_output_eligibility(approved_sources(), values, [])
        self.assertFalse(result["eligible_for_controlled_test_artifact_preparation"])
        self.assertIn("missing required approval: commercial_approved", result["blockers"])

    def test_open_exception_blocks_and_approved_exception_requires_reason(self):
        result = evaluate_output_eligibility(
            approved_sources(),
            approvals(),
            [
                {"id": "EX-1", "status": "OPEN", "reason": ""},
                {"id": "EX-2", "status": "APPROVED_EXCEPTION", "reason": ""},
            ],
        )
        self.assertFalse(result["eligible_for_controlled_test_artifact_preparation"])
        self.assertIn("unresolved exception: EX-1", result["blockers"])
        self.assertIn("approved exception requires reason: EX-2", result["blockers"])

    def test_resolved_and_reasoned_approved_exception_are_allowed(self):
        result = evaluate_output_eligibility(
            approved_sources(),
            approvals(),
            [
                {"id": "EX-1", "status": "RESOLVED", "reason": "corrected upstream"},
                {"id": "EX-2", "status": "APPROVED_EXCEPTION", "reason": "estimator accepts documented variance"},
            ],
        )
        self.assertTrue(result["eligible_for_controlled_test_artifact_preparation"])

    def test_manifest_is_review_only_and_does_not_claim_artifact_or_import(self):
        manifest = build_output_manifest(approved_sources(), approvals(), [], "test-import-v1")
        self.assertEqual(manifest["manifest_version"], "1")
        self.assertEqual(manifest["output_version"], "test-import-v1")
        self.assertFalse(manifest["artifact_created"])
        self.assertFalse(manifest["heavybid_import_attempted"])
        self.assertFalse(manifest["control_flags"]["HEAVYBID_IMPORT_VALIDATED"])

    def test_manifest_requires_explicit_version(self):
        with self.assertRaisesRegex(ValueError, "output_version is required"):
            build_output_manifest(approved_sources(), approvals(), [], "")


if __name__ == "__main__":
    unittest.main()
