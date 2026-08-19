from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from audit_engine import audit


class ExternalCrashRegressions(unittest.TestCase):
    def test_ext003_negative_hundred_percent_markup_is_controlled(self):
        result = audit({"Estimate": [{"Description": "Markup case", "Quantity": "1", "Unit": "LS", "Rate": "1", "Amount": "1", "Markup %": "-100%", "Margin %": "0%"}]})
        self.assertIn("R016", {finding["rule_id"] for finding in result["findings"]})

    def test_ext004_nonfinite_rates_are_controlled_not_crashes(self):
        for rate in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(rate=rate):
                result = audit({"Estimate": [{"Description": "Numeric case", "Quantity": "1", "Unit": "EA", "Rate": rate, "Amount": "1"}]})
                self.assertIn("R004", {finding["rule_id"] for finding in result["findings"]})

    def test_nonfinite_optional_numeric_is_explicit(self):
        result = audit({"Estimate": [{"Description": "Optional numeric", "Quantity": "1", "Unit": "EA", "Rate": "1", "Amount": "Infinity"}]})
        self.assertIn("R017", {finding["rule_id"] for finding in result["findings"]})

