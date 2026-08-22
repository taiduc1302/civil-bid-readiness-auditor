from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from audit_engine import audit, normalize_unit


class UomAndReviewMetricTests(unittest.TestCase):
    def test_safe_uom_spelling_variants_normalize(self):
        self.assertEqual(normalize_unit("HRS"), "hr")
        self.assertEqual(normalize_unit("Hours"), "hr")
        self.assertEqual(normalize_unit("EACH"), "ea")
        self.assertEqual(normalize_unit("Lump Sum"), "ls")
        self.assertEqual(normalize_unit("Metres"), "m")
        self.assertEqual(normalize_unit("m^3"), "m3")

    def test_distinct_earthwork_measurement_bases_remain_distinct(self):
        self.assertEqual(normalize_unit("BCY"), "bcy")
        self.assertEqual(normalize_unit("LCY"), "lcy")
        self.assertEqual(normalize_unit("CCY"), "ccy")
        self.assertNotEqual(normalize_unit("BCY"), normalize_unit("LCY"))
        self.assertNotEqual(normalize_unit("LCY"), normalize_unit("CCY"))

    def test_short_t_is_metric_tonne_not_us_ton(self):
        self.assertEqual(normalize_unit("t"), "tonne")
        self.assertEqual(normalize_unit("TON"), "ton")
        self.assertNotEqual(normalize_unit("t"), normalize_unit("TON"))

    def test_equivalent_uom_variants_do_not_trigger_inconsistent_unit(self):
        result = audit({"Rows": [
            {"Description": "Operator", "Quantity": "1", "Unit": "HR", "Rate": "50"},
            {"Description": "Operator", "Quantity": "2", "Unit": "Hours", "Rate": "50"},
        ]})
        self.assertNotIn("R010", {finding["rule_id"] for finding in result["findings"]})

    def test_rate_peer_group_uses_normalized_uom(self):
        result = audit({"Rows": [
            {"Description": "Excavator", "Quantity": "1", "Unit": "HR", "Rate": "180", "Resource Type": "Equipment"},
            {"Description": "Dozer", "Quantity": "1", "Unit": "HRS", "Rate": "190", "Resource Type": "Equipment"},
            {"Description": "Loader", "Quantity": "1", "Unit": "Hour", "Rate": "200", "Resource Type": "Equipment"},
            {"Description": "Crane", "Quantity": "1", "Unit": "Hours", "Rate": "2500", "Resource Type": "Equipment"},
        ]})
        outliers = [finding for finding in result["findings"] if finding["rule_id"] == "R015"]
        self.assertEqual(len(outliers), 1)
        self.assertIn("unit hr", outliers[0]["evidence"])

    def test_review_metrics_count_unique_affected_rows(self):
        result = audit({"Rows": [
            {"Description": "Pipe", "Quantity": "", "Unit": "EA", "Rate": ""},
            {"Description": "Rock", "Quantity": "1", "Unit": "TON", "Rate": "10"},
            {"Description": "Labour", "Quantity": "1", "Unit": "HR", "Rate": "50"},
            {"Description": "Mobilization", "Quantity": "1", "Unit": "LS", "Rate": "1000"},
        ]})
        metrics = result["review_metrics"]
        self.assertEqual(metrics["affected_rows"], 1)
        self.assertEqual(metrics["priority_rows"], 1)
        self.assertEqual(metrics["affected_row_percent"], 25.0)
        self.assertEqual(metrics["finding_count"], 2)
        self.assertEqual(metrics["status"], "High-priority review required")

    def test_clean_estimate_has_clear_status(self):
        result = audit({"Rows": [
            {"Description": "Pipe", "Quantity": "10", "Unit": "M", "Rate": "100"},
            {"Description": "Manhole", "Quantity": "1", "Unit": "EA", "Rate": "5000"},
        ]})
        metrics = result["review_metrics"]
        self.assertEqual(metrics["status"], "No deterministic findings")
        self.assertEqual(metrics["affected_rows"], 0)
        self.assertEqual(metrics["affected_row_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
