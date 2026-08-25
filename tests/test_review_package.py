from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions, set_disposition
from review_package import build_review_package, package_manifest


class ReviewPackageTests(unittest.TestCase):
    def session(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        sheets = parse_upload(sample.name, sample.read_bytes())
        result = audit(sheets)
        dispositions = default_dispositions(result)
        set_disposition(dispositions, 1, "Reviewed", "Checked against source")
        return {
            "filename": sample.name,
            "result": result,
            "dispositions": dispositions,
            "mappings": {},
        }

    def test_package_is_deterministic_and_contains_core_exports(self):
        session = self.session()
        first, filename = build_review_package(session)
        second, second_filename = build_review_package(session)
        self.assertEqual(first, second)
        self.assertEqual(filename, second_filename)
        self.assertTrue(filename.endswith("_review_package_v1.zip"))

        with zipfile.ZipFile(io.BytesIO(first)) as book:
            self.assertEqual(
                set(book.namelist()),
                {"README.txt", "findings.csv", "manifest.json", "review.csv", "summary.html"},
            )
            manifest = json.loads(book.read("manifest.json"))
            self.assertEqual(manifest["package_format"], "civil-estimate-review-package")
            self.assertEqual(manifest["package_version"], 1)
            self.assertFalse(manifest["contents"]["original_estimate_bytes_included"])
            self.assertFalse(manifest["contents"]["original_reference_bytes_included"])
            self.assertFalse(manifest["safety"]["HEAVYBID_IMPORT_VALIDATED"])
            self.assertIn(b"Reviewed", book.read("review.csv"))
            self.assertIn(b"Required human review", book.read("summary.html"))

    def test_reference_checks_are_included_only_when_present(self):
        session = self.session()
        session["reference_results"] = [{
            "source_row": 2,
            "reference_type": "resource",
            "status": "NO_MATCH",
            "code": "M-1",
            "reference_code": "",
            "reference_unit": "",
            "message": "Code is not present in the supplied governed reference.",
        }]
        session["reference_sources"] = ["resource_reference.csv"]
        data, _ = build_review_package(session)
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            self.assertIn("references.csv", book.namelist())
            manifest = json.loads(book.read("manifest.json"))
            self.assertTrue(manifest["contents"]["reference_checks_included"])
            self.assertEqual(manifest["reference_status_counts"], {"NO_MATCH": 1})

    def test_manifest_requires_no_heavybid_claims(self):
        manifest = package_manifest(self.session())
        self.assertTrue(manifest["safety"]["NOT_PRODUCTION_READY"])
        self.assertTrue(manifest["safety"]["NOT_ESTIMATOR_VALIDATED"])
        self.assertFalse(manifest["safety"]["HEAVYBID_IMPORT_VALIDATED"])
        self.assertFalse(manifest["safety"]["bid_certified"])


if __name__ == "__main__":
    unittest.main()
