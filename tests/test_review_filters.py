from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from review_filters import filter_findings, filter_options, group_findings, sort_findings


class ReviewFilterTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "findings": [
                {"id": 1, "severity": "High", "rule_id": "R001", "sheet": "Estimate", "row": 4, "field": "rate", "message": "Missing rate", "evidence": "", "recommended_action": "Review rate"},
                {"id": 2, "severity": "Medium", "rule_id": "R015", "sheet": "Estimate", "row": 7, "field": "rate", "message": "Rate outlier", "evidence": "2500", "recommended_action": "Check unit"},
                {"id": 3, "severity": "Critical", "rule_id": "R001", "sheet": "Alternate", "row": 2, "field": "description", "message": "Blank description", "evidence": "", "recommended_action": "Add description"},
                {"id": 4, "severity": "High", "rule_id": "R009", "sheet": "Estimate", "row": 3, "field": "rate", "message": "Conflicting rate", "evidence": "", "recommended_action": "Review rate"},
            ]
        }
        self.dispositions = {
            1: {"status": "Open", "reason": ""},
            2: {"status": "Suppressed", "reason": "Known allowance"},
            3: {"status": "Needs correction", "reason": "Fix before review"},
            4: {"status": "Reviewed", "reason": "Checked"},
        }

    def test_priority_filter_is_critical_and_high_only(self):
        filtered = filter_findings(self.result, self.dispositions, severity="Priority")
        self.assertEqual([item["id"] for item in filtered], [1, 3, 4])

    def test_filters_compose(self):
        filtered = filter_findings(
            self.result,
            self.dispositions,
            severity="Critical",
            review_status="Needs correction",
            rule_id="R001",
            sheet="Alternate",
        )
        self.assertEqual([item["id"] for item in filtered], [3])

    def test_text_search_includes_review_reason(self):
        filtered = filter_findings(self.result, self.dispositions, text="allowance")
        self.assertEqual([item["id"] for item in filtered], [2])

    def test_filtering_does_not_mutate_inputs(self):
        findings_before = [dict(item) for item in self.result["findings"]]
        dispositions_before = {key: dict(value) for key, value in self.dispositions.items()}
        filter_findings(self.result, self.dispositions, severity="High")
        self.assertEqual(self.result["findings"], findings_before)
        self.assertEqual(self.dispositions, dispositions_before)

    def test_filter_options_are_stable(self):
        options = filter_options(self.result)
        self.assertEqual(options["rules"], ["R001", "R009", "R015"])
        self.assertEqual(options["sheets"], ["Alternate", "Estimate"])

    def test_priority_sort_is_deterministic_and_non_mutating(self):
        original = list(self.result["findings"])
        sorted_findings = sort_findings(self.result["findings"], self.dispositions, "priority")
        self.assertEqual([item["id"] for item in sorted_findings], [3, 4, 1, 2])
        self.assertEqual(self.result["findings"], original)

    def test_source_rule_and_review_status_sorts(self):
        self.assertEqual([item["id"] for item in sort_findings(self.result["findings"], self.dispositions, "source")], [3, 4, 1, 2])
        self.assertEqual([item["id"] for item in sort_findings(self.result["findings"], self.dispositions, "rule")], [3, 1, 4, 2])
        self.assertEqual([item["id"] for item in sort_findings(self.result["findings"], self.dispositions, "review_status")], [3, 1, 4, 2])

    def test_unknown_sort_fails_safe_to_priority(self):
        expected = sort_findings(self.result["findings"], self.dispositions, "priority")
        actual = sort_findings(self.result["findings"], self.dispositions, "not-a-sort")
        self.assertEqual([item["id"] for item in actual], [item["id"] for item in expected])

    def test_grouping_preserves_current_order_and_adds_composition(self):
        ordered = sort_findings(self.result["findings"], self.dispositions, "priority")
        groups = group_findings(ordered, self.dispositions, "sheet")
        self.assertEqual(
            [label for label, _ in groups],
            [
                "Alternate — Critical 1 · Needs correction 1",
                "Estimate — High 2 · Medium 1 · Open 1",
            ],
        )
        self.assertEqual([[item["id"] for item in items] for _, items in groups], [[3], [4, 1, 2]])

    def test_review_status_grouping_and_unknown_group(self):
        ordered = sort_findings(self.result["findings"], self.dispositions, "review_status")
        groups = group_findings(ordered, self.dispositions, "review_status")
        self.assertEqual(
            [label for label, _ in groups],
            [
                "Needs correction — Critical 1 · Needs correction 1",
                "Open — High 1 · Open 1",
                "Reviewed — High 1",
                "Suppressed — Medium 1",
            ],
        )
        self.assertEqual(group_findings(ordered, self.dispositions, "not-a-group"), [("", ordered)])


if __name__ == "__main__":
    unittest.main()
