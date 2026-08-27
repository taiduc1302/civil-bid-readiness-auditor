from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from group_summaries import findings_group_summary, reference_group_summary


class GroupSummaryTests(unittest.TestCase):
    def test_findings_summary_counts_severity_and_attention_only(self):
        findings = [
            {"id": 1, "severity": "Critical"},
            {"id": 2, "severity": "High"},
            {"id": 3, "severity": "High"},
            {"id": 4, "severity": "Low"},
        ]
        dispositions = {
            1: {"status": "Open", "reason": ""},
            2: {"status": "Needs correction", "reason": "fix"},
            3: {"status": "Reviewed", "reason": ""},
            4: {"status": "Accepted", "reason": ""},
        }
        summary = findings_group_summary(findings, dispositions)
        self.assertEqual(
            summary,
            "4 findings · Critical 1 · High 2 · Low 1 · Open 1 · Needs correction 1",
        )
        self.assertNotIn("ready", summary.casefold())
        self.assertNotIn("approved", summary.casefold())

    def test_findings_summary_defaults_missing_state_to_open(self):
        self.assertEqual(
            findings_group_summary([{"id": 7, "severity": "Medium"}], {}),
            "1 finding · Medium 1 · Open 1",
        )

    def test_reference_summary_reports_visible_status_composition(self):
        items = [
            {"status": "NO_MATCH"},
            {"status": "NO_MATCH"},
            {"status": "UNIT_MISMATCH"},
            {"status": "MATCH"},
        ]
        self.assertEqual(
            reference_group_summary(items),
            "4 checks · NO_MATCH 2 · UNIT_MISMATCH 1 · MATCH 1",
        )

    def test_empty_group_summaries_are_descriptive_only(self):
        self.assertEqual(findings_group_summary([], {}), "0 findings")
        self.assertEqual(reference_group_summary([]), "0 checks")


if __name__ == "__main__":
    unittest.main()
