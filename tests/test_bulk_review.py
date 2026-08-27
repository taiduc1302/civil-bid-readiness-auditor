from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from bulk_review import (
    PLAN_FORMAT,
    PLAN_VERSION,
    _plan_digest,
    apply_bulk_review_plan,
    build_bulk_review_plan,
    finding_set_fingerprint,
)


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

    @staticmethod
    def rehash(plan: dict) -> dict:
        plan = copy.deepcopy(plan)
        core = {key: value for key, value in plan.items() if key != "plan_sha256"}
        plan["plan_sha256"] = _plan_digest(core)
        return plan

    def plan(self, ids=(1, 2), status="Accepted", reason="Selected findings reviewed"):
        return build_bulk_review_plan(
            self.result,
            self.dispositions,
            ids,
            status,
            reason,
            ownership_acknowledged=True,
        )

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
        self.assertRegex(plan["plan_sha256"], r"^[0-9a-f]{64}$")

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

    def test_apply_returns_new_map_and_changes_only_explicit_targets(self):
        result_before = copy.deepcopy(self.result)
        dispositions_before = copy.deepcopy(self.dispositions)
        plan = self.plan()
        applied = apply_bulk_review_plan(self.result, self.dispositions, plan)

        self.assertIsNot(applied, self.dispositions)
        self.assertEqual(applied[1], {"status": "Accepted", "reason": "Selected findings reviewed"})
        self.assertEqual(applied[2], {"status": "Accepted", "reason": "Selected findings reviewed"})
        self.assertEqual(applied[3], self.dispositions[3])
        self.assertEqual(self.result, result_before)
        self.assertEqual(self.dispositions, dispositions_before)

    def test_apply_can_materialize_default_open_state_on_copy_only(self):
        dispositions = {2: {"status": "Reviewed", "reason": "Checked manually"}}
        plan = build_bulk_review_plan(
            self.result,
            dispositions,
            [1],
            "Reviewed",
            ownership_acknowledged=True,
        )
        applied = apply_bulk_review_plan(self.result, dispositions, plan)
        self.assertNotIn(1, dispositions)
        self.assertEqual(applied[1], {"status": "Reviewed", "reason": ""})

    def test_apply_rejects_unsupported_plan_identity_and_missing_digest(self):
        plan = self.plan()
        wrong_version = copy.deepcopy(plan)
        wrong_version["plan_version"] = PLAN_VERSION - 1
        with self.assertRaisesRegex(ValueError, "format/version"):
            apply_bulk_review_plan(self.result, self.dispositions, wrong_version)

        missing_digest = copy.deepcopy(plan)
        missing_digest.pop("plan_sha256")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            apply_bulk_review_plan(self.result, self.dispositions, missing_digest)

    def test_apply_rejects_plan_content_tampering(self):
        plan = self.plan()
        plan["target_status"] = "Reviewed"
        with self.assertRaisesRegex(ValueError, "SHA-256 does not match"):
            apply_bulk_review_plan(self.result, self.dispositions, plan)

    def test_apply_rejects_rehashed_relaxed_safety_flags_and_bad_count(self):
        for flag in ("apply_automatically", "mutates_deterministic_findings", "mutates_reference_results", "changes_score"):
            with self.subTest(flag=flag):
                tampered = self.plan()
                tampered[flag] = True
                tampered = self.rehash(tampered)
                with self.assertRaisesRegex(ValueError, "automatic application|relaxed safety flag"):
                    apply_bulk_review_plan(self.result, self.dispositions, tampered)

        bad_count = self.plan()
        bad_count["target_count"] = 99
        bad_count = self.rehash(bad_count)
        with self.assertRaisesRegex(ValueError, "target count"):
            apply_bulk_review_plan(self.result, self.dispositions, bad_count)

    def test_apply_rejects_deterministic_finding_drift(self):
        plan = self.plan()
        changed = copy.deepcopy(self.result)
        changed["findings"][2]["message"] = "Unselected finding also changed"
        with self.assertRaisesRegex(ValueError, "finding set changed"):
            apply_bulk_review_plan(changed, self.dispositions, plan)

    def test_apply_rejects_current_review_state_drift(self):
        plan = self.plan()
        changed = copy.deepcopy(self.dispositions)
        changed[1] = {"status": "Reviewed", "reason": "Someone reviewed it after planning"}
        changed_before = copy.deepcopy(changed)
        with self.assertRaisesRegex(ValueError, "current review state changed"):
            apply_bulk_review_plan(self.result, changed, plan)
        self.assertEqual(changed, changed_before)

    def test_apply_revalidates_target_status_rules_even_with_rehashed_plan(self):
        plan = self.plan()
        plan["target_status"] = "Suppressed"
        plan["reason"] = ""
        plan = self.rehash(plan)
        with self.assertRaisesRegex(ValueError, "require a review reason"):
            apply_bulk_review_plan(self.result, self.dispositions, plan)

    def test_apply_rejects_rehashed_expected_state_id_mismatch(self):
        plan = self.plan()
        plan["expected_current_states"][0]["id"] = 3
        plan = self.rehash(plan)
        with self.assertRaisesRegex(ValueError, "ids do not match"):
            apply_bulk_review_plan(self.result, self.dispositions, plan)


if __name__ == "__main__":
    unittest.main()
