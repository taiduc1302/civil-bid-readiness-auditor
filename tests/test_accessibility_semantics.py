from __future__ import annotations

import http.client
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from server import Handler, ThreadingHTTPServer


class AccessibilitySemanticsTests(unittest.TestCase):
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

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        status = response.status
        conn.close()
        return status, payload

    def assert_document_semantics(self, page: bytes) -> None:
        self.assertIn(b"<html lang='en'>", page)
        self.assertIn(b"class='global-skip' href='#main-content'", page)
        self.assertIn(b"<main id='main-content' tabindex='-1'>", page)
        self.assertEqual(page.count(b"href='#main-content'"), 1)

    def test_home_has_language_main_landmark_skip_link_and_status_semantics(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assert_document_semantics(page)
        self.assertIn(b"class='notice' role='status' aria-live='polite'", page)

    def test_guide_keeps_existing_content_inside_shared_accessible_shell(self):
        status, page = self.request("GET", "/guide")
        self.assertEqual(status, 200)
        self.assert_document_semantics(page)
        self.assertIn(b"Fictional training data only", page)
        self.assertIn(b"role='status' aria-live='polite'", page)

    def test_not_found_error_is_an_assertive_alert(self):
        status, page = self.request("GET", "/definitely-not-a-route")
        self.assertEqual(status, 404)
        self.assert_document_semantics(page)
        self.assertIn(b"class='error' role='alert' aria-live='assertive' tabindex='-1'", page)
        self.assertIn(b"Page not found", page)

    def test_package_verification_error_uses_same_alert_semantics(self):
        status, page = self.request("POST", "/verify-package", b"", {"Content-Length": "0"})
        self.assertEqual(status, 400)
        self.assert_document_semantics(page)
        self.assertIn(b"class='error' role='alert' aria-live='assertive' tabindex='-1'", page)
        self.assertIn(b"Verification failed", page)


if __name__ == "__main__":
    unittest.main()
