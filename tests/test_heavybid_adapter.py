from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from heavybid_adapter import (
    PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT,
    adapter_contract,
    detect_heavybid_style_export,
    map_heavybid_style_headers,
)


class HeavyBidStyleAdapterTests(unittest.TestCase):
    def fixture(self):
        path = ROOT / "samples" / "synthetic_heavybid_style_resource_export.csv"
        sheets = parse_upload(path.name, path.read_bytes())
        sheet_name = next(iter(sheets))
        headers = [header for header in sheets[sheet_name][0] if not header.startswith("__")]
        mapping = map_heavybid_style_headers(headers)
        return sheets, sheet_name, headers, mapping

    def test_supported_fixture_is_detected(self):
        _, _, headers, mapping = self.fixture()
        self.assertTrue(detect_heavybid_style_export(headers))
        self.assertEqual(mapping["bid_item"], "Bid Item")
        self.assertEqual(mapping["activity"], "Activity Code")
        self.assertEqual(mapping["resource_type"], "Resource Type")
        self.assertEqual(mapping["resource_code"], "Resource Code")
        self.assertEqual(mapping["description"], "Resource Description")

    def test_detection_fails_closed_without_hierarchy_signature(self):
        headers = ["Description", "Quantity", "Unit", "Rate"]
        self.assertFalse(detect_heavybid_style_export(headers))
        mapping = map_heavybid_style_headers(headers)
        self.assertNotIn("bid_item", mapping)
        self.assertNotIn("activity", mapping)

    def test_header_mapping_is_not_fuzzy(self):
        mapping = map_heavybid_style_headers([
            "Bid Item-ish", "Activity-ish", "Resource Kind", "Resource Description",
            "Quantity", "Unit", "Rate",
        ])
        self.assertNotIn("bid_item", mapping)
        self.assertNotIn("activity", mapping)
        self.assertNotIn("resource_type", mapping)

    def test_contract_disables_inference_and_conversions(self):
        contract = adapter_contract()
        self.assertEqual(contract["profile"], PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT)
        self.assertFalse(contract["direct_database_access"])
        self.assertFalse(contract["fuzzy_header_matching"])
        self.assertFalse(contract["infers_missing_values"])
        self.assertFalse(contract["validates_company_codebook"])
        self.assertFalse(contract["converts_units"])

    def test_fixture_runs_through_generic_audit(self):
        sheets, sheet_name, _, mapping = self.fixture()
        result = audit(sheets, {sheet_name: mapping})
        self.assertEqual(result["rows_reviewed"], 22)
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        for expected in ("R003", "R005", "R008", "R011", "R015"):
            self.assertIn(expected, rule_ids)
        self.assertEqual(result["review_metrics"]["status"], "High-priority review required")

    def test_hour_aliases_share_equipment_peer_group(self):
        sheets, sheet_name, _, mapping = self.fixture()
        result = audit(sheets, {sheet_name: mapping})
        outliers = [finding for finding in result["findings"] if finding["rule_id"] == "R015"]
        self.assertEqual(len(outliers), 1)
        self.assertIn("unit hr", outliers[0]["evidence"])
        self.assertIn("2600", outliers[0]["evidence"])

    def test_bcy_and_lcy_are_not_converted_or_collapsed(self):
        sheets, sheet_name, _, mapping = self.fixture()
        result = audit(sheets, {sheet_name: mapping})
        inconsistent_units = [finding for finding in result["findings"] if finding["rule_id"] == "R010"]
        self.assertFalse(any("bcy" in f["evidence"] and "lcy" in f["evidence"] for f in inconsistent_units))


if __name__ == "__main__":
    unittest.main()
