from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from bulk_review import PLAN_FORMAT, PLAN_VERSION, build_bulk_review_plan, finding_set_fingerprint


class BulkReviewPlanTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "score": 42,
            "findings": [
                {
                    "id": 1,
                    "severity": "High",
                    "rule_id": "R001",
                    "sheet": "Estimate",
                    "row": 4,
                    "field": "rate",
                    "message": "Missing rate",
                },
                {
                    "id": 2,
                    "severity": "Medium",
                    "rule_id": "R015",
                    "sheet": "Estimate",
                    "row": 7,
                    "field": "rate",
                    "message": "Rate outlier",
                },
                {
                    "id": 3,
                    "severity": "Low",
                    "rule_id": "R017",
                    "sheet": "Alternate",
                    "row": 2,
                    "field": "description",
                    "message": "Formula-like text",
                },
            ],
        }
        self.dispositions = {
            1: {"status": "Open", "reason": ""},
            2: {"status": "Reviewed", "reason": "Checked manually"},
            3: {"status": "Needs correction", "reason": "Fix text"},
        }

    def test_plan_requires_explicit_human_ownership(self):
        with self.assertRaisesRegex(ValueError, "human-ownership"):
            build_bulk_review_plan(self.result, self.dispositions, [1], "Reviewed")
        with self.assertRaisesRegex(ValueError, "human-ownership"):
            build_bulk_review_plan(
                self.result, self.dispositions, [1], "Reviewed", ownership_acknowledged=1
            )

    def test_plan_targets_only_explicit_ids_and_records_current_states(self):
        plan = build_bulk_review_plan(
            self.result,
            self.dispositions,
            [2, 1],
            "Accepted",
            "Estimator reviewed selected rows",
            ownership_acknowledged=True,
        )
        self.assertEqual(plan["plan_format"], PLAN_FORMAT)
        self.assertEqual(plan["plan_version"], PLAN_VERSION)
        self.assertEqual(plan["target_ids"], [2, 1])
        self.assertEqual(plan["target_count"], 2)
        self.assertEqual(plan["target_status"], "Accepted")
        self.assertEqual(plan["reason"], "Estimator reviewed selected rows")
        self.assertEqual(
            plan["expected_current_states"],
            [
                {"id": 2, "status": "Reviewed", "reason": "Checked manually"},
                {"id": 1, "status": "Open", "reason": ""},
            ],
        )
        self.assertFalse(plan["apply_automatically"])
        self.assertFalse(plan["mutates_deterministic_findings"])
        self.assertFalse(plan["mutates_reference_results"])
        self.assertFalse(plan["changes_score"])
        self.assertRegex(plan["finding_set_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(plan["target_findings_sha256"], r"^[0-9a-f]{64}$")

    def test_suppression_uses_existing_reason_rule(self):
        with self.assertRaisesRegex(ValueError, "require a review reason"):
            build_bulk_review_plan(
                self.result,
                self.dispositions,
                [1, 2],
                "Suppressed",
                ownership_acknowledged=True,
            )
        plan = build_bulk_review_plan(
            self.result,
            self.dispositions,
            [1, 2],
            "Suppressed",
            "Known synthetic duplicate condition",
            ownership_acknowledged=True,
        )
        self.assertEqual(plan["target_status"], "Suppressed")
        self.assertEqual(plan["reason"], "Known synthetic duplicate condition")

    def test_empty_duplicate_unknown_and_invalid_ids_fail_closed(self):
        cases = [
            ([], "at least one"),
            ([1, 1], "duplicate"),
            ([1, "1"], "duplicate"),
            ([99], "Unknown"),
            ([0], "Invalid"),
            ([True], "booleans"),
        ]
        for ids, message in cases:
            with self.subTest(ids=ids):
                with self.assertRaisesRegex(ValueError, message):
                    build_bulk_review_plan(
                        self.result,
                        self.dispositions,
                        ids,
                        "Reviewed",
                        ownership_acknowledged=True,
                    )

    def test_string_is_not_implicit_id_collection_and_invalid_status_fails(self):
        with self.assertRaisesRegex(ValueError, "explicit collection"):
            build_bulk_review_plan(
                self.result,
                self.dispositions,
                "123",
                "Reviewed",
                ownership_acknowledged=True,
            )
        with self.assertRaisesRegex(ValueError, "Unsupported review status"):
            build_bulk_review_plan(
                self.result,
                self.dispositions,
                [1],
                "Approve everything",
                ownership_acknowledged=True,
            )

    def test_plan_is_pure_and_does_not_mutate_inputs(self):
        result_before = copy.deepcopy(self.result)
        dispositions_before = copy.deepcopy(self.dispositions)
        build_bulk_review_plan(
            self.result,
            self.dispositions,
            [1, 3],
            "Reviewed",
            ownership_acknowledged=True,
        )
        self.assertEqual(self.result, result_before)
        self.assertEqual(self.dispositions, dispositions_before)

    def test_finding_set_fingerprint_is_stable_and_detects_identity_drift(self):
        first = finding_set_fingerprint(self.result)
        reordered = copy.deepcopy(self.result)
        reordered["findings"] = list(reversed(reordered["findings"]))
        self.assertEqual(finding_set_fingerprint(reordered), first)

        changed = copy.deepcopy(self.result)
        changed["findings"][0]["message"] = "Different deterministic finding"
        self.assertNotEqual(finding_set_fingerprint(changed), first)

    def test_no_findings_cannot_produce_bulk_plan(self):
        with self.assertRaisesRegex(ValueError, "no findings"):
            build_bulk_review_plan(
                {"findings": []},
                {},
                [1],
                "Reviewed",
                ownership_acknowledged=True,
            )


if __name__ == "__main__":
    unittest.main()
