from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import parse_upload
from heavybid_adapter import PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT
from server import detected_mapping, mapping_page


class ServerProfileDetectionTests(unittest.TestCase):
    def fixture_session(self):
        path = ROOT / "samples" / "synthetic_heavybid_style_resource_export.csv"
        return {
            "filename": path.name,
            "sheets": parse_upload(path.name, path.read_bytes()),
            "created": time.monotonic(),
        }

    def test_detected_mapping_prefers_supported_profile(self):
        session = self.fixture_session()
        rows = next(iter(session["sheets"].values()))
        headers = [header for header in rows[0] if not header.startswith("__")]
        mapping, profile = detected_mapping(headers)
        self.assertEqual(profile, PROFILE_HEAVYBID_STYLE_RESOURCE_EXPORT)
        self.assertEqual(mapping["bid_item"], "Bid Item")
        self.assertEqual(mapping["activity"], "Activity Code")
        self.assertEqual(mapping["resource_type"], "Resource Type")
        self.assertEqual(mapping["resource_code"], "Resource Code")
        self.assertEqual(mapping["description"], "Resource Description")

    def test_generic_headers_do_not_claim_heavybid_style_profile(self):
        mapping, profile = detected_mapping(["Description", "Quantity", "Unit", "Rate"])
        self.assertIsNone(profile)
        self.assertEqual(mapping["description"], "Description")
        self.assertEqual(mapping["quantity"], "Quantity")
        self.assertEqual(mapping["unit"], "Unit")
        self.assertEqual(mapping["rate"], "Rate")

    def test_mapping_page_discloses_preselection_and_manual_override(self):
        body = mapping_page("fixture-token", self.fixture_session())
        self.assertIn(b"Structured resource-export profile recognized", body)
        self.assertIn(b"Review or override every mapping before audit", body)
        self.assertIn(b"name='map__synthetic_heavybid_style_resource_export__bid_item'", body)
        self.assertIn(b"value='Bid Item' selected", body)
        self.assertIn(b"value='Activity Code' selected", body)
        self.assertIn(b"value='Resource Type' selected", body)
        self.assertIn(b"value='Resource Code' selected", body)


if __name__ == "__main__":
    unittest.main()
