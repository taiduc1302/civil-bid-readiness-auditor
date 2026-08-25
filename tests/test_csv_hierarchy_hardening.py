from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_csv_bytes


class CsvAndHierarchyHardeningTests(unittest.TestCase):
    def test_csv_header_scan_skips_metadata_and_preserves_source_rows(self):
        data = (
            "Synthetic estimate export,,,,\n"
            "Project,Example,,,\n"
            ",,,,\n"
            "Description,Quantity,Unit,Rate,Amount\n"
            "Pipe,2,M,10,20\n"
            "Valve,1,EA,25,25\n"
        ).encode("utf-8")
        sheets = parse_csv_bytes(data, "metadata.csv")
        rows = sheets["metadata"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Description"], "Pipe")
        self.assertEqual(rows[0]["__source_row"], "5")
        self.assertEqual(rows[1]["__source_row"], "6")

    def test_csv_low_confidence_keeps_first_readable_row_for_manual_mapping(self):
        data = (
            "Custom A,Custom B,Custom C,Custom D\n"
            "Pipe,2,M,10\n"
        ).encode("utf-8")
        rows = parse_csv_bytes(data, "custom.csv")["custom"]
        self.assertEqual(rows[0]["Custom A"], "Pipe")
        self.assertEqual(rows[0]["__source_row"], "2")

    def test_r009_sees_conflict_across_resource_codes_in_same_activity_and_class(self):
        rows = [
            {
                "Description": "Granular base",
                "Quantity": "100",
                "Unit": "TON",
                "Rate": "30",
                "Bid Item": "800",
                "Activity": "BASE",
                "Resource Type": "Material",
                "Resource Code": "MAT-A",
                "__source_row": "2",
            },
            {
                "Description": "Granular base",
                "Quantity": "100",
                "Unit": "TON",
                "Rate": "35",
                "Bid Item": "800",
                "Activity": "BASE",
                "Resource Type": "Material",
                "Resource Code": "MAT-B",
                "__source_row": "3",
            },
        ]
        mapping = {
            "description": "Description",
            "quantity": "Quantity",
            "unit": "Unit",
            "rate": "Rate",
            "bid_item": "Bid Item",
            "activity": "Activity",
            "resource_type": "Resource Type",
            "resource_code": "Resource Code",
        }
        result = audit({"Estimate": rows}, {"Estimate": mapping})
        r009_rows = {finding["row"] for finding in result["findings"] if finding["rule_id"] == "R009"}
        self.assertEqual(r009_rows, {2, 3})
        self.assertFalse(any(finding["rule_id"] == "R008" for finding in result["findings"]))

    def test_r010_sees_unit_conflict_across_resource_codes_in_same_activity_and_class(self):
        rows = [
            {"Description": "Excavation", "Quantity": "100", "Unit": "BCY", "Rate": "10", "Bid Item": "200", "Activity": "EXC", "Resource Type": "Material", "Resource Code": "EARTH-A", "__source_row": "2"},
            {"Description": "Excavation", "Quantity": "100", "Unit": "LCY", "Rate": "10", "Bid Item": "200", "Activity": "EXC", "Resource Type": "Material", "Resource Code": "EARTH-B", "__source_row": "3"},
        ]
        mapping = {"description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate", "bid_item": "Bid Item", "activity": "Activity", "resource_type": "Resource Type", "resource_code": "Resource Code"}
        result = audit({"Estimate": rows}, {"Estimate": mapping})
        r010_rows = {finding["row"] for finding in result["findings"] if finding["rule_id"] == "R010"}
        self.assertEqual(r010_rows, {2, 3})

    def test_different_activities_remain_separate_conflict_contexts(self):
        rows = [
            {"Description": "Granular base", "Quantity": "100", "Unit": "TON", "Rate": "30", "Bid Item": "800", "Activity": "BASE-A", "Resource Type": "Material", "Resource Code": "MAT-A", "__source_row": "2"},
            {"Description": "Granular base", "Quantity": "100", "Unit": "TON", "Rate": "35", "Bid Item": "800", "Activity": "BASE-B", "Resource Type": "Material", "Resource Code": "MAT-B", "__source_row": "3"},
        ]
        mapping = {"description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate", "bid_item": "Bid Item", "activity": "Activity", "resource_type": "Resource Type", "resource_code": "Resource Code"}
        result = audit({"Estimate": rows}, {"Estimate": mapping})
        self.assertFalse(any(finding["rule_id"] in {"R009", "R010"} for finding in result["findings"]))


if __name__ == "__main__":
    unittest.main()
