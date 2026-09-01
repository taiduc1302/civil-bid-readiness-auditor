from __future__ import annotations

import copy
import csv
import hashlib
import http.client
import io
import json
import sys
import threading
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_delta import compare_review_packages
from review_delta_export import build_review_delta_export
from review_package import build_review_package
from server import Handler, SESSIONS, ThreadingHTTPServer


class ReviewDeltaExportTests(unittest.TestCase):
    def session(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }

    def package(self, session):
        return build_review_package(session)[0]

    def comparison(self):
        earlier = self.session()
        later = copy.deepcopy(earlier)
        later["dispositions"][1] = {"status": "Reviewed", "reason": "Checked."}
        return compare_review_packages(
            "earlier.zip", self.package(earlier), "later.zip", self.package(later)
        )

    def test_same_comparison_produces_byte_identical_integrity_hashed_bundle(self):
        result = self.comparison()
        first, first_name = build_review_delta_export(result)
        second, second_name = build_review_delta_export(result)
        self.assertEqual(first_name, "review_delta_evidence_v1.zip")
        self.assertEqual(first_name, second_name)
        self.assertEqual(first, second)

        with zipfile.ZipFile(io.BytesIO(first)) as book:
            self.assertEqual(
                sorted(book.namelist()),
                [
                    "README.txt",
                    "finding_changes.csv",
                    "integrity.json",
                    "manifest.json",
                    "reference_changes.csv",
                    "reference_metadata_changes.csv",
                    "review_delta.json",
                ],
            )
            manifest = json.loads(book.read("manifest.json"))
            integrity = json.loads(book.read("integrity.json"))
            full = json.loads(book.read("review_delta.json"))
            self.assertEqual(manifest["export_format"], "civil-estimate-review-delta-export")
            self.assertEqual(manifest["export_version"], 1)
            self.assertTrue(manifest["safety"]["evidence_drift_only"])
            self.assertFalse(manifest["safety"]["session_created"])
            self.assertFalse(manifest["safety"]["correctness_inferred"])
            self.assertFalse(manifest["safety"]["readiness_inferred"])
            self.assertFalse(manifest["safety"]["heavybid_import_validated"])
            self.assertFalse(manifest["contents"]["original_review_packages_included"])
            self.assertFalse(manifest["contents"]["operational_session_evidence_included"])
            self.assertFalse(full["session_created"])
            self.assertFalse(full["re_audit_performed"])
            self.assertFalse(full["heavybid_import_validated"])

            self.assertNotIn("integrity.json", integrity["members"])
            for name, evidence in integrity["members"].items():
                payload = book.read(name)
                self.assertEqual(evidence["size_bytes"], len(payload))
                self.assertEqual(evidence["sha256"], hashlib.sha256(payload).hexdigest())

    def test_csv_cells_are_spreadsheet_safe_and_full_delta_is_machine_readable(self):
        result = self.comparison()
        changed = next(item for item in result["finding_changes"] if item["change_type"] == "REVIEW_CHANGED")
        changed["after_review"]["reason"] = "=HYPERLINK(\"https://example.invalid\")"
        bundle, _ = build_review_delta_export(result)
        with zipfile.ZipFile(io.BytesIO(bundle)) as book:
            rows = list(csv.DictReader(io.StringIO(book.read("finding_changes.csv").decode("utf-8"))))
            row = next(item for item in rows if item["change_type"] == "REVIEW_CHANGED")
            self.assertTrue(row["after_review_reason"].startswith("'="))
            full = json.loads(book.read("review_delta.json"))
            self.assertEqual(full["comparison_format"], "civil-estimate-review-delta")
            self.assertEqual(len(full["finding_changes"]), len(result["finding_changes"]))

    def test_relaxed_comparison_safety_flags_fail_closed(self):
        result = self.comparison()
        for flag in (
            "session_created",
            "re_audit_performed",
            "correctness_inferred",
            "readiness_inferred",
            "heavybid_import_validated",
        ):
            with self.subTest(flag=flag):
                changed = copy.deepcopy(result)
                changed[flag] = True
                with self.assertRaisesRegex(ValueError, flag):
                    build_review_delta_export(changed)


class ReviewDeltaExportHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join()
        cls.httpd.server_close()

    def setUp(self):
        SESSIONS.clear()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        conn.close()
        return status, response_headers, payload

    def package(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        session = {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }
        return build_review_package(session)[0]

    def multipart(self, earlier: bytes, later: bytes):
        boundary = "----review-delta-export-boundary"
        chunks: list[bytes] = []
        for field, filename, payload in (
            ("earlier_package", "earlier.zip", earlier),
            ("later_package", "later.zip", later),
        ):
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode()
            )
            chunks.append(b"Content-Type: application/zip\r\n\r\n")
            chunks.append(payload)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        return body, {
            "Content-Type": f'multipart/form-data; boundary="{boundary}"',
            "Content-Length": str(len(body)),
        }

    def test_compare_form_exposes_export_and_download_creates_no_session(self):
        status, _, page = self.request("GET", "/compare-review-packages")
        self.assertEqual(status, 200)
        self.assertIn(b"formaction='/export-review-delta'", page)
        self.assertIn(b"Download evidence bundle", page)

        package = self.package()
        body, headers = self.multipart(package, package)
        status, response_headers, bundle = self.request("POST", "/export-review-delta", body, headers)
        self.assertEqual(status, 200)
        self.assertIn("application/zip", response_headers["Content-Type"])
        self.assertIn("review_delta_evidence_v1.zip", response_headers["Content-Disposition"])
        self.assertEqual(SESSIONS, {})
        with zipfile.ZipFile(io.BytesIO(bundle)) as book:
            manifest = json.loads(book.read("manifest.json"))
        self.assertEqual(manifest["finding_counts"]["UNCHANGED"], 14)
        self.assertFalse(manifest["safety"]["session_created"])

    def test_tampered_later_package_fails_before_export_and_creates_no_session(self):
        package = self.package()
        body, headers = self.multipart(package, b"not-a-zip")
        status, response_headers, page = self.request("POST", "/export-review-delta", body, headers)
        self.assertEqual(status, 400)
        self.assertIn("text/html", response_headers["Content-Type"])
        self.assertIn(b"Comparison failed", page)
        self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
