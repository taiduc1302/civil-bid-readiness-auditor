from __future__ import annotations

import http.client
import re
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from server import Handler, SESSIONS, ThreadingHTTPServer


class DemoKitServerTests(unittest.TestCase):
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

    def test_guide_exposes_structured_demo_and_reference_downloads(self):
        status, _, page = self.request("GET", "/guide")
        self.assertEqual(status, 200)
        self.assertIn(b"action='/sample-structured'", page)
        self.assertIn(b"href='/demo/reference/activity'", page)
        self.assertIn(b"href='/demo/reference/resource'", page)
        self.assertIn(b"References are never auto-applied", page)
        self.assertEqual(SESSIONS, {})

    def test_fixed_reference_downloads_are_synthetic_csvs_and_create_no_session(self):
        status, headers, activity = self.request("GET", "/demo/reference/activity")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("synthetic_activity_reference.csv", headers["Content-Disposition"])
        self.assertTrue(activity.startswith(b"activity_code,"))

        status, headers, resource = self.request("GET", "/demo/reference/resource")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("synthetic_resource_reference.csv", headers["Content-Disposition"])
        self.assertTrue(resource.startswith(b"resource_code,"))
        self.assertEqual(SESSIONS, {})

    def test_structured_demo_opens_editable_mapping_without_auto_applying_references(self):
        status, _, page = self.request("POST", "/sample-structured", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        self.assertIn(b"Map columns", page)
        self.assertIn(b"Structured resource-export profile recognized", page)
        self.assertIn(b"HeavyBid-style header mapping was preselected", page)
        self.assertIn(b"Bid Item", page)
        self.assertIn(b"Activity Code", page)
        self.assertIn(b"Resource Code", page)

        token_match = re.search(rb"name='token' value='([^']+)'", page)
        self.assertIsNotNone(token_match)
        token = token_match.group(1).decode()
        self.assertIn(token, SESSIONS)
        session = SESSIONS[token]
        self.assertEqual(session["filename"], "synthetic_heavybid_style_resource_export.csv")
        self.assertNotIn("result", session)
        self.assertNotIn("reference_results", session)
        self.assertNotIn("reference_metadata", session)

    def test_unlisted_demo_reference_route_is_not_exposed(self):
        status, _, page = self.request("GET", "/demo/reference/other")
        self.assertEqual(status, 404)
        self.assertIn(b"Page not found", page)
        self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
