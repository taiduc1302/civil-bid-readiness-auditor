from __future__ import annotations

import http.client
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from onboarding import guide_body
from server import Handler, ThreadingHTTPServer


class OnboardingTests(unittest.TestCase):
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

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        status = response.status
        conn.close()
        return status, payload

    def test_guide_body_covers_current_review_workflow_and_safety(self):
        body = guide_body()
        for phrase in (
            "Run synthetic sample",
            "Sort by priority",
            "group by sheet",
            "Suppressed requires a reason",
            "SHA-256",
            "NOT_ESTABLISHED_BY_APP",
            "Download the review package ZIP",
            "HEAVYBID_IMPORT_VALIDATED=false",
        ):
            self.assertIn(phrase, body)

    def test_home_links_to_local_guide(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Open fictional onboarding walkthrough", body)
        self.assertIn(b"href='/guide'", body)

    def test_guide_page_is_local_and_starts_existing_sample_flow(self):
        status, body = self.request("GET", "/guide")
        self.assertEqual(status, 200)
        self.assertIn(b"Fictional onboarding walkthrough", body)
        self.assertIn(b"Fictional training data only", body)
        self.assertIn(b"action='/sample'", body)
        self.assertIn(b"NOT_PRODUCTION_READY=true", body)
        self.assertIn(b"NOT_ESTIMATOR_VALIDATED=true", body)
        self.assertIn(b"HEAVYBID_IMPORT_VALIDATED=false", body)

        status, sample_page = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        self.assertIn(b"Map columns", sample_page)


if __name__ == "__main__":
    unittest.main()
