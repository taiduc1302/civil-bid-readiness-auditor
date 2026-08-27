from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from demo_kit import reference_fixture, structured_estimate


class DemoKitTests(unittest.TestCase):
    def test_structured_estimate_is_fixed_bundled_fixture(self):
        name, data = structured_estimate()
        self.assertEqual(name, "synthetic_heavybid_style_resource_export.csv")
        header = data.decode("utf-8").splitlines()[0]
        self.assertIn("Bid Item", header)
        self.assertIn("Activity Code", header)
        self.assertIn("Resource Code", header)

    def test_activity_and_resource_references_are_fixed_synthetic_csvs(self):
        activity_name, activity_data = reference_fixture("activity")
        resource_name, resource_data = reference_fixture("resource")
        self.assertEqual(activity_name, "synthetic_activity_reference.csv")
        self.assertEqual(resource_name, "synthetic_resource_reference.csv")
        activity_headers = next(csv.reader(io.StringIO(activity_data.decode("utf-8"))))
        resource_headers = next(csv.reader(io.StringIO(resource_data.decode("utf-8"))))
        self.assertIn("activity_code", activity_headers)
        self.assertIn("resource_code", resource_headers)
        self.assertIn("unit", activity_headers)
        self.assertIn("unit", resource_headers)

    def test_unknown_reference_role_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported fictional reference role"):
            reference_fixture("other")


if __name__ == "__main__":
    unittest.main()
