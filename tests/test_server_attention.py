from __future__ import annotations

import http.client
import re
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from server import Handler, ThreadingHTTPServer


class ServerAttentionTests(unittest.TestCase):
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
        status, body = self.request("POST", "/audit", encoded, {
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(encoded)),
        })
        self.assertEqual(status, 200)
        return token, body

    def test_initial_attention_summary_is_review_state_not_readiness(self):
        token, body = self.audited_sample()
        self.assertIn(b"Review attention summary", body)
        self.assertIn(b"<strong>14</strong><br>Open findings", body)
        self.assertIn(b"<strong>0</strong><br>Needs correction", body)
        self.assertIn(b"<strong>0</strong><br>Reference exceptions", body)
        self.assertIn(b"No governed reference checks are loaded", body)
        self.assertIn(b"do not establish estimator approval, reference authority, or bid readiness", body)
        self.assertIn(b"href='#attention'", body)
        self.assertIn(token.encode(), body)

    def test_needs_correction_updates_attention_without_changing_total_findings(self):
        token, _ = self.audited_sample()
        form = urlencode({"token": token, "status__1": "Needs correction", "reason__1": "Fix source row"}).encode()
        status, body = self.request("POST", "/review", form, {
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(form)),
        })
        self.assertEqual(status, 200)
        self.assertIn(b"<strong>13</strong><br>Open findings", body)
        self.assertIn(b"<strong>1</strong><br>Needs correction", body)
        self.assertIn(b"14 finding(s) are currently Open or Needs correction", body)
        self.assertIn(b"Total findings</div>", body)

    def test_filtered_empty_state_does_not_claim_no_underlying_findings(self):
        token, _ = self.audited_sample()
        query = urlencode({"token": token, "q": "definitely-no-such-finding-text"})
        status, body = self.request("GET", f"/results?{query}")
        self.assertEqual(status, 200)
        self.assertIn(b"Visible:</strong> 0 of 14 findings", body)
        self.assertIn(b"No findings match the current filters. The underlying audit result is unchanged.", body)
        self.assertIn(b"<strong>14</strong><br>Open findings", body)


if __name__ == "__main__":
    unittest.main()
