from __future__ import annotations

import http.client
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from review_evidence_navigation import review_evidence_navigation
from server import Handler, SESSIONS, ThreadingHTTPServer


class ReviewEvidenceNavigationTests(unittest.TestCase):
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

    def request(self, path: str) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        payload = response.read()
        status = response.status
        conn.close()
        return status, payload

    def test_navigation_block_has_all_routes_and_explicit_no_carry_boundary(self):
        block = review_evidence_navigation("Review Delta")
        self.assertIn("/compare-review-packages", block)
        self.assertIn("/verify-review-delta", block)
        self.assertIn("/review-timeline", block)
        self.assertIn("No evidence is carried between these pages", block)
        self.assertIn("does not persist or transfer uploaded ZIP bytes", block)
        self.assertIn("verifies its own inputs independently", block)
        self.assertNotIn("value=", block)
        self.assertNotIn("type='hidden'", block)

    def test_all_evidence_pages_cross_link_without_creating_session(self):
        for path in ("/compare-review-packages", "/verify-review-delta", "/review-timeline"):
            with self.subTest(path=path):
                status, page = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(b"Review evidence views", page)
                self.assertIn(b"href='/compare-review-packages'", page)
                self.assertIn(b"href='/verify-review-delta'", page)
                self.assertIn(b"href='/review-timeline'", page)
                self.assertIn(b"No evidence is carried between these pages", page)
                self.assertIn(b"Re-select evidence at the destination", page)
                self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
