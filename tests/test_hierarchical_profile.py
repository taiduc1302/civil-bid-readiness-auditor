from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from export_profiles import PROFILE_STRUCTURED_CIVIL, mapping_for_profile


class HierarchicalProfileTests(unittest.TestCase):
    def fixture_result(self):
        path = ROOT / "samples" / "synthetic_hierarchical_civil_estimate.csv"
        sheets = parse_upload(path.name, path.read_bytes())
        sheet_name = next(iter(sheets))
        headers = [header for header in sheets[sheet_name][0] if not header.startswith("__")]
        mapping = mapping_for_profile(PROFILE_STRUCTURED_CIVIL, headers)
        return audit(sheets, {sheet_name: mapping})

    def test_profile_maps_required_and_hierarchy_fields(self):
        headers = [
            "Bid Item No", "Activity Code", "Resource Type", "Resource Code",
            "Description", "Quantity", "Unit", "Rate", "Amount", "Category",
        ]
        mapping = mapping_for_profile(PROFILE_STRUCTURED_CIVIL, headers)
        self.assertEqual(mapping["description"], "Description")
        self.assertEqual(mapping["quantity"], "Quantity")
        self.assertEqual(mapping["unit"], "Unit")
        self.assertEqual(mapping["rate"], "Rate")
        self.assertEqual(mapping["bid_item"], "Bid Item No")
        self.assertEqual(mapping["activity"], "Activity Code")
        self.assertEqual(mapping["resource_type"], "Resource Type")
        self.assertEqual(mapping["resource_code"], "Resource Code")

    def test_profile_does_not_guess_missing_columns(self):
        mapping = mapping_for_profile(PROFILE_STRUCTURED_CIVIL, ["Description", "Quantity", "Unit"])
        self.assertNotIn("rate", mapping)
        self.assertNotIn("resource_type", mapping)

    def test_unknown_profile_is_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown export profile"):
            mapping_for_profile("not-a-profile", ["Description"])

    def test_hierarchical_fixture_exercises_expected_rules(self):
        result = self.fixture_result()
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        for rule_id in ("R003", "R005", "R008", "R011", "R015"):
            self.assertIn(rule_id, rule_ids)

    def test_hourly_uom_variants_form_one_rate_peer_group(self):
        result = self.fixture_result()
        outliers = [finding for finding in result["findings"] if finding["rule_id"] == "R015"]
        self.assertEqual(len(outliers), 1)
        self.assertIn("unit hr", outliers[0]["evidence"])
        self.assertIn("2500", outliers[0]["evidence"])

    def test_bcy_and_lcy_remain_separate(self):
        result = self.fixture_result()
        unit_findings = [finding for finding in result["findings"] if finding["rule_id"] == "R010"]
        self.assertFalse(any("bcy" in finding["evidence"] and "lcy" in finding["evidence"] for finding in unit_findings))

    def test_fixture_reports_review_metrics(self):
        result = self.fixture_result()
        metrics = result["review_metrics"]
        self.assertEqual(result["rows_reviewed"], 31)
        self.assertGreater(metrics["affected_rows"], 0)
        self.assertGreater(metrics["priority_rows"], 0)
        self.assertEqual(metrics["status"], "High-priority review required")


if __name__ == "__main__":
    unittest.main()
