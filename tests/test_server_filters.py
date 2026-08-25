from __future__ import annotations

import http.client
import re
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from server import Handler, ThreadingHTTPServer


class ServerFilterTests(unittest.TestCase):
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

    def audited_sample(self):
        status, body = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        token = re.search(rb"name='token' value='([^']+)'", body).group(1).decode()
        mappings = {"token": token}
        for field, header in {
            "description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate",
            "amount": "Amount", "category": "Category", "markup_pct": "Markup %", "margin_pct": "Margin %",
        }.items():
            mappings[f"map__synthetic_civil_estimate__{field}"] = header
        encoded = urlencode(mappings).encode()
        status, _ = self.request("POST", "/audit", encoded, {
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded)),
        })
        self.assertEqual(status, 200)
        return token

    def test_results_get_exposes_filters_and_priority_view(self):
        token = self.audited_sample()
        status, body = self.request("GET", f"/results?token={token}&severity=Priority")
        self.assertEqual(status, 200)
        self.assertIn(b"Review filters", body)
        self.assertIn(b"Visible:</strong> 11 of 14 findings", body)
        self.assertEqual(body.count(b"id='finding-"), 11)
        self.assertIn(b"Back to filters", body)

    def test_review_status_filter_preserves_saved_state(self):
        token = self.audited_sample()
        form = urlencode({
            "token": token,
            "status__1": "Suppressed",
            "reason__1": "Known review exception",
        }).encode()
        status, _ = self.request("POST", "/review", form, {
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(form)),
        })
        self.assertEqual(status, 200)

        status, body = self.request("GET", f"/results?token={token}&review_status=Suppressed")
        self.assertEqual(status, 200)
        self.assertIn(b"Visible:</strong> 1 of 14 findings", body)
        self.assertIn(b"id='finding-1'", body)
        self.assertIn(b"Known review exception", body)

    def test_text_search_filters_visible_rows(self):
        token = self.audited_sample()
        status, body = self.request("GET", f"/results?token={token}&q=R011")
        self.assertEqual(status, 200)
        visible = re.search(rb"Visible:</strong> (\d+) of 14 findings", body)
        self.assertIsNotNone(visible)
        self.assertGreater(int(visible.group(1)), 0)
        self.assertLess(int(visible.group(1)), 14)

    def test_expired_results_token_is_safe(self):
        status, body = self.request("GET", "/results?token=missing")
        self.assertEqual(status, 404)
        self.assertIn(b"no longer available", body)


if __name__ == "__main__":
    unittest.main()
