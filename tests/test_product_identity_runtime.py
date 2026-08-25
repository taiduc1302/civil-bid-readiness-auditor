from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, management_summary_html
from server import home


class ProductIdentityRuntimeTests(unittest.TestCase):
    def test_home_uses_public_review_title_not_legacy_bid_readiness_title(self):
        body = home()
        self.assertIn(b"Civil Estimate Review Auditor", body)
        self.assertNotIn(b"Civil Bid Readiness Auditor", body)
        self.assertIn(b"Required human review", body)

    def test_management_summary_uses_public_review_title_and_keeps_disclaimer(self):
        rows = [{"Description": "Pipe", "Quantity": "2", "Unit": "M", "Rate": "10", "Amount": "20", "__source_row": "2"}]
        mapping = {"description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate", "amount": "Amount"}
        result = audit({"Estimate": rows}, {"Estimate": mapping})
        report = management_summary_html(result, "synthetic.csv")
        self.assertIn(b"Civil Estimate Review Auditor", report)
        self.assertNotIn(b"Civil Bid Readiness Auditor", report)
        self.assertIn(b"Required human review", report)


if __name__ == "__main__":
    unittest.main()
