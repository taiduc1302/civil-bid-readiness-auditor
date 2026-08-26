from __future__ import annotations

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


class PackageVerificationUiTests(unittest.TestCase):
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
        conn.close()
        return status, payload

    def multipart(self, filename: str | None, payload: bytes = b""):
        boundary = "----package-verification-boundary"
        chunks: list[bytes] = []
        if filename is not None:
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(
                f'Content-Disposition: form-data; name="review_package"; filename="{filename}"\r\n'.encode()
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

    def review_package(self) -> tuple[bytes, str]:
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return build_review_package({
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        })

    def test_home_and_get_verifier_are_available_without_session(self):
        status, home = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Verify review package ZIP", home)
        self.assertIn(b"href='/verify-package'", home)

        status, page = self.request("GET", "/verify-package")
        self.assertEqual(status, 200)
        self.assertIn(b"Verify a review package", page)
        self.assertIn(b"action='/verify-package'", page)
        self.assertIn(b"does not restore", page)
        self.assertEqual(SESSIONS, {})

    def test_valid_package_verifies_without_creating_session(self):
        package, filename = self.review_package()
        body, headers = self.multipart(filename, package)
        before = dict(SESSIONS)
        status, page = self.request("POST", "/verify-package", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Integrity verification passed", page)
        self.assertIn(filename.encode(), page)
        self.assertIn(b"civil-estimate-review-package", page)
        self.assertIn(b"No review session was restored", page)
        self.assertIn(b"does not establish estimate correctness", page)
        self.assertEqual(SESSIONS, before)

    def test_tampered_package_fails_without_creating_session(self):
        package, filename = self.review_package()
        tampered = bytearray(package)
        tampered[len(tampered) // 2] ^= 1
        body, headers = self.multipart(filename, bytes(tampered))
        status, page = self.request("POST", "/verify-package", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"Verification failed", page)
        self.assertNotIn(b"Integrity verification passed", page)
        self.assertEqual(SESSIONS, {})

    def test_missing_or_wrong_extension_fails_safely(self):
        body, headers = self.multipart(None)
        status, page = self.request("POST", "/verify-package", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"Choose a review-package ZIP", page)

        package, _ = self.review_package()
        body, headers = self.multipart("review.txt", package)
        status, page = self.request("POST", "/verify-package", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"must be a ZIP file", page)
        self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
