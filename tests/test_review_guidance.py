from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from review_guidance import review_attention_summary


class ReviewGuidanceTests(unittest.TestCase):
    def test_open_and_needs_correction_are_attention_not_readiness(self):
        result = {"findings": [{"id": 1}, {"id": 2}, {"id": 3}]}
        dispositions = {
            1: {"status": "Open", "reason": ""},
            2: {"status": "Needs correction", "reason": "Fix"},
            3: {"status": "Reviewed", "reason": "Checked"},
        }
        summary = review_attention_summary(result, dispositions)
        self.assertEqual(summary["finding_attention_count"], 2)
        self.assertEqual(summary["open_count"], 1)
        self.assertEqual(summary["needs_correction_count"], 1)
        self.assertFalse(summary["approval_inferred"])
        self.assertFalse(summary["bid_readiness_inferred"])
        self.assertIn("human-review attention", summary["finding_message"])

    def test_no_findings_is_explicitly_not_proof_of_correctness(self):
        summary = review_attention_summary({"findings": []}, {})
        self.assertEqual(summary["findings_total"], 0)
        self.assertIn("not proof", summary["finding_message"].casefold())
        self.assertIn("No governed reference checks", summary["reference_message"])

    def test_no_open_attention_does_not_claim_approval(self):
        result = {"findings": [{"id": 1}, {"id": 2}]}
        dispositions = {
            1: {"status": "Reviewed", "reason": ""},
            2: {"status": "Accepted", "reason": ""},
        }
        summary = review_attention_summary(result, dispositions)
        self.assertEqual(summary["finding_attention_count"], 0)
        self.assertIn("not estimator approval", summary["finding_message"])

    def test_reference_exceptions_count_every_non_match_status(self):
        reference_results = [
            {"status": "MATCH"},
            {"status": "NO_MATCH"},
            {"status": "UNIT_MISMATCH"},
            {"status": "NOT_CHECKED"},
        ]
        summary = review_attention_summary({"findings": []}, {}, reference_results)
        self.assertEqual(summary["reference_checks_total"], 4)
        self.assertEqual(summary["reference_exception_count"], 3)
        self.assertIn("3 governed reference check", summary["reference_message"])
        self.assertFalse(summary["reference_authority_inferred"])

    def test_all_reference_matches_still_do_not_establish_authority(self):
        summary = review_attention_summary(
            {"findings": []}, {}, [{"status": "MATCH"}, {"status": "MATCH"}]
        )
        self.assertEqual(summary["reference_exception_count"], 0)
        self.assertIn("do not establish reference authority", summary["reference_message"])


if __name__ == "__main__":
    unittest.main()
