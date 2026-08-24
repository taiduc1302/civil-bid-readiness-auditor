from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from finding_review import default_dispositions, findings_review_csv, review_metrics, set_disposition, validate_disposition


class FindingReviewTests(unittest.TestCase):
    def result(self):
        return {"findings": [
            {"id": 1, "severity": "High", "rule_id": "R003", "sheet": "Estimate", "row": 2, "field": "quantity", "message": "Quantity is zero.", "evidence": "0", "recommended_action": "Confirm."},
            {"id": 2, "severity": "Medium", "rule_id": "R015", "sheet": "Estimate", "row": 5, "field": "rate", "message": "Rate outlier.", "evidence": "rate 2500", "recommended_action": "Check rate."},
        ]}

    def test_new_findings_default_to_open(self):
        dispositions = default_dispositions(self.result())
        self.assertEqual(dispositions[1], {"status": "Open", "reason": ""})
        self.assertEqual(review_metrics(self.result(), dispositions)["Open"], 2)

    def test_supported_statuses_can_be_recorded(self):
        dispositions = default_dispositions(self.result())
        set_disposition(dispositions, 1, "Needs correction", "Estimator will revise quantity")
        set_disposition(dispositions, 2, "Accepted", "Checked against quote")
        self.assertEqual(dispositions[1]["status"], "Needs correction")
        self.assertEqual(dispositions[2]["status"], "Accepted")

    def test_suppression_requires_reason(self):
        with self.assertRaisesRegex(ValueError, "require a review reason"):
            validate_disposition("Suppressed", "")
        self.assertEqual(validate_disposition("Suppressed", "Known intentional allowance"), ("Suppressed", "Known intentional allowance"))

    def test_unknown_status_and_finding_fail_closed(self):
        dispositions = default_dispositions(self.result())
        with self.assertRaisesRegex(ValueError, "Unsupported review status"):
            set_disposition(dispositions, 1, "Ignore")
        with self.assertRaisesRegex(ValueError, "Unknown finding id"):
            set_disposition(dispositions, 999, "Reviewed")

    def test_review_export_contains_status_and_reason(self):
        result = self.result()
        dispositions = default_dispositions(result)
        set_disposition(dispositions, 1, "Suppressed", "Intentional zero placeholder")
        data = findings_review_csv(result, dispositions)
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        self.assertEqual(rows[0]["review_status"], "Suppressed")
        self.assertEqual(rows[0]["review_reason"], "Intentional zero placeholder")
        self.assertEqual(rows[1]["review_status"], "Open")

    def test_review_export_protects_formula_like_reason(self):
        result = self.result()
        dispositions = default_dispositions(result)
        set_disposition(dispositions, 1, "Reviewed", "=HYPERLINK(\"x\")")
        data = findings_review_csv(result, dispositions).decode("utf-8")
        self.assertIn("'=HYPERLINK", data)


if __name__ == "__main__":
    unittest.main()
