from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from review_filters import filter_findings, filter_options


class ReviewFilterTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "findings": [
                {"id": 1, "severity": "High", "rule_id": "R001", "sheet": "Estimate", "row": 4, "field": "rate", "message": "Missing rate", "evidence": "", "recommended_action": "Review rate"},
                {"id": 2, "severity": "Medium", "rule_id": "R015", "sheet": "Estimate", "row": 7, "field": "rate", "message": "Rate outlier", "evidence": "2500", "recommended_action": "Check unit"},
                {"id": 3, "severity": "Critical", "rule_id": "R001", "sheet": "Alternate", "row": 2, "field": "description", "message": "Blank description", "evidence": "", "recommended_action": "Add description"},
            ]
        }
        self.dispositions = {
            1: {"status": "Open", "reason": ""},
            2: {"status": "Suppressed", "reason": "Known allowance"},
            3: {"status": "Needs correction", "reason": "Fix before review"},
        }

    def test_priority_filter_is_critical_and_high_only(self):
        filtered = filter_findings(self.result, self.dispositions, severity="Priority")
        self.assertEqual([item["id"] for item in filtered], [1, 3])

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
        self.assertEqual(options["rules"], ["R001", "R015"])
        self.assertEqual(options["sheets"], ["Alternate", "Estimate"])


if __name__ == "__main__":
    unittest.main()
