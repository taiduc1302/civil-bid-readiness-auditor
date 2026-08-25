from __future__ import annotations

import csv
import http.client
import io
import re
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from server import Handler, ThreadingHTTPServer


class ServerReviewTests(unittest.TestCase):
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
        status, response_headers = response.status, dict(response.getheaders())
        conn.close()
        return status, response_headers, payload

    def audited_sample(self):
        status, _, body = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        token = re.search(rb"name='token' value='([^']+)'", body).group(1).decode()
        mappings = {"token": token}
        for field, header in {
            "description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate",
            "amount": "Amount", "category": "Category", "markup_pct": "Markup %", "margin_pct": "Margin %",
        }.items():
            mappings[f"map__synthetic_civil_estimate__{field}"] = header
        encoded = urlencode(mappings).encode()
        status, _, body = self.request("POST", "/audit", encoded, {
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded)),
        })
        self.assertEqual(status, 200)
        return token, body

    def test_results_page_exposes_review_controls(self):
        token, body = self.audited_sample()
        self.assertIn(b"Findings review", body)
        self.assertIn(b"Save visible review states", body)
        self.assertIn(b"Download review CSV", body)
        self.assertIn(b"status__1", body)
        self.assertIn(b"Open", body)
        self.assertIn(token.encode(), body)

    def test_review_state_can_be_saved_and_exported(self):
        token, _ = self.audited_sample()
        form = urlencode({
            "token": token,
            "status__1": "Suppressed",
            "reason__1": "Intentional test condition",
        }).encode()
        status, _, body = self.request("POST", "/review", form, {
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(form)),
        })
        self.assertEqual(status, 200)
        self.assertIn(b"Review states saved", body)
        self.assertIn(b"Intentional test condition", body)

        status, headers, data = self.request("GET", f"/export/review?token={token}")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        first = next(row for row in rows if row["id"] == "1")
        self.assertEqual(first["review_status"], "Suppressed")
        self.assertEqual(first["review_reason"], "Intentional test condition")

    def test_suppression_without_reason_is_rejected_atomically(self):
        token, _ = self.audited_sample()
        form = urlencode({"token": token, "status__1": "Suppressed", "reason__1": ""}).encode()
        status, _, body = self.request("POST", "/review", form, {
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(form)),
        })
        self.assertEqual(status, 400)
        self.assertIn(b"Suppressed findings require a review reason", body)

        status, _, data = self.request("GET", f"/export/review?token={token}")
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        first = next(row for row in rows if row["id"] == "1")
        self.assertEqual(first["review_status"], "Open")
        self.assertEqual(first["review_reason"], "")


if __name__ == "__main__":
    unittest.main()
