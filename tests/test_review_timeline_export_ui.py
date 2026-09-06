from __future__ import annotations

import copy
import http.client
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_delta import compare_review_packages
from review_delta_export import build_review_delta_export
from review_package import build_review_package
from review_timeline_export import verify_review_timeline_export
from server import Handler, SESSIONS, ThreadingHTTPServer


class ReviewTimelineExportUiTests(unittest.TestCase):
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
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        conn.close()
        return status, response_headers, payload

    def packages(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        base = {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }
        middle = copy.deepcopy(base)
        later = copy.deepcopy(base)
        middle["dispositions"][1] = {"status": "Reviewed", "reason": "middle"}
        later["dispositions"][1] = {"status": "Reviewed", "reason": "middle"}
        later["dispositions"][2] = {"status": "Needs correction", "reason": "later"}
        return tuple(build_review_package(item)[0] for item in (base, middle, later))

    def delta(self, earlier_name, earlier, later_name, later):
        result = compare_review_packages(earlier_name, earlier, later_name, later)
        return build_review_delta_export(result)[0]

    def multipart(self, uploads):
        boundary = "----timeline-export-download-test"
        chunks: list[bytes] = []
        for filename, payload in uploads:
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(
                f'Content-Disposition: form-data; name="delta_export"; filename="{filename}"\r\n'.encode()
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

    def test_get_requires_fresh_selection_and_creates_no_session(self):
        status, _, page = self.request("GET", "/export-review-timeline")
        self.assertEqual(status, 200)
        self.assertIn(b"Download Review Timeline evidence export", page)
        self.assertIn(b"Fresh verification required", page)
        self.assertIn(b"name='delta_export'", page)
        self.assertIn(b"multiple required", page)
        self.assertIn(b"No uploads, verified flags, preview model", page)
        self.assertIn(b"HEAVYBID_IMPORT_VALIDATED=false", page)
        self.assertNotIn(b"name='timeline_export'", page)
        self.assertEqual(SESSIONS, {})

    def test_valid_reversed_delta_uploads_return_independently_verified_zip_without_session(self):
        a, b, c = self.packages()
        ab = self.delta("A.zip", a, "B.zip", b)
        bc = self.delta("B-renamed.zip", b, "C.zip", c)
        body, headers = self.multipart([
            ("bc.delta.zip", bc),
            ("ab.delta.zip", ab),
        ])
        status, response_headers, payload = self.request(
            "POST", "/export-review-timeline", body, headers
        )
        self.assertEqual(status, 200)
        self.assertEqual(response_headers["Content-Type"], "application/zip")
        self.assertIn("review_timeline_evidence_v1.zip", response_headers["Content-Disposition"])
        self.assertEqual(int(response_headers["Content-Length"]), len(payload))

        verified = verify_review_timeline_export(payload)
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["snapshot_count"], 3)
        self.assertEqual(verified["transition_count"], 2)
        self.assertFalse(verified["heavybid_import_validated"])
        self.assertEqual(SESSIONS, {})

    def test_invalid_or_insufficient_inputs_fail_html_without_session(self):
        a, b, _c = self.packages()
        ab = self.delta("A.zip", a, "B.zip", b)
        body, headers = self.multipart([("only.delta.zip", ab)])
        status, response_headers, page = self.request(
            "POST", "/export-review-timeline", body, headers
        )
        self.assertEqual(status, 400)
        self.assertIn("text/html", response_headers["Content-Type"])
        self.assertIn(b"Timeline export failed", page)
        self.assertIn(b"Choose at least 2", page)
        self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
