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
from review_package import build_review_package
from server import Handler, SESSIONS, ThreadingHTTPServer


class ReviewDeltaUiTests(unittest.TestCase):
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
        status = response.status
        response_headers = dict(response.getheaders())
        conn.close()
        return status, response_headers, payload

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

    def multipart(self, earlier: tuple[str, bytes] | None, later: tuple[str, bytes] | None):
        boundary = "----review-delta-boundary"
        chunks: list[bytes] = []
        for field, item in (("earlier_package", earlier), ("later_package", later)):
            if item is None:
                continue
            filename, payload = item
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

    def test_home_and_compare_page_are_available_without_session(self):
        status, _, home = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Compare review snapshots", home)
        self.assertIn(b"href='/compare-review-packages'", home)

        status, _, page = self.request("GET", "/compare-review-packages")
        self.assertEqual(status, 200)
        self.assertIn(b"Earlier review-package ZIP", page)
        self.assertIn(b"Later review-package ZIP", page)
        self.assertEqual(SESSIONS, {})

    def test_identical_packages_compare_without_creating_session(self):
        package = self.package(self.session())
        body, headers = self.multipart(("earlier.zip", package), ("later.zip", package))
        status, _, page = self.request("POST", "/compare-review-packages", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Review Delta result", page)
        self.assertIn(b"Evidence drift only", page)
        self.assertIn(b"Unchanged 14", page)
        self.assertEqual(SESSIONS, {})

    def test_review_only_change_is_rendered_neutrally(self):
        earlier = self.session()
        later = copy.deepcopy(earlier)
        later["dispositions"][1] = {"status": "Reviewed", "reason": "Checked."}
        body, headers = self.multipart(
            ("earlier.zip", self.package(earlier)),
            ("later.zip", self.package(later)),
        )
        status, _, page = self.request("POST", "/compare-review-packages", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"REVIEW_CHANGED", page)
        self.assertIn(b"Open", page)
        self.assertIn(b"Reviewed", page)
        self.assertNotIn(b"improved", page.lower())
        self.assertEqual(SESSIONS, {})

    def test_missing_second_package_and_invalid_zip_fail_without_session(self):
        package = self.package(self.session())
        body, headers = self.multipart(("earlier.zip", package), None)
        status, _, page = self.request("POST", "/compare-review-packages", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"Choose both an Earlier and a Later", page)
        self.assertEqual(SESSIONS, {})

        body, headers = self.multipart(("earlier.zip", package), ("later.zip", b"not-a-zip"))
        status, _, page = self.request("POST", "/compare-review-packages", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"Comparison failed", page)
        self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
