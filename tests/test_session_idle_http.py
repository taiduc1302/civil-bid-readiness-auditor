from __future__ import annotations

import http.client
import re
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import server_legacy as legacy
from server import Handler, SESSIONS, ThreadingHTTPServer


class SessionIdleHttpTests(unittest.TestCase):
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

    def post_form(self, path: str, pairs):
        encoded = urlencode(pairs).encode()
        return self.request(
            "POST",
            path,
            encoded,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": str(len(encoded)),
            },
        )

    def audited_sample(self):
        status, _, body = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        token = re.search(rb"name='token' value='([^']+)'", body).group(1).decode()
        mappings = [("token", token)]
        for field, header in {
            "description": "Description",
            "quantity": "Quantity",
            "unit": "Unit",
            "rate": "Rate",
            "amount": "Amount",
            "category": "Category",
            "markup_pct": "Markup %",
            "margin_pct": "Margin %",
        }.items():
            mappings.append((f"map__synthetic_civil_estimate__{field}", header))
        status, _, _ = self.post_form("/audit", mappings)
        self.assertEqual(status, 200)
        return token

    def test_results_access_refreshes_idle_timeout(self):
        token = self.audited_sample()
        self.assertIn("last_access", SESSIONS[token])
        previous = time.monotonic() - legacy.SESSION_TTL_SECONDS + 5.0
        SESSIONS[token]["last_access"] = previous

        status, _, _ = self.request("GET", f"/results?token={token}")
        self.assertEqual(status, 200)
        self.assertGreater(SESSIONS[token]["last_access"], previous)

    def test_idle_session_expires_on_next_lookup(self):
        token = self.audited_sample()
        SESSIONS[token]["last_access"] = time.monotonic() - legacy.SESSION_TTL_SECONDS - 1.0

        status, _, body = self.request("GET", f"/results?token={token}")
        self.assertEqual(status, 404)
        self.assertIn(b"temporary audit session is no longer available", body)
        self.assertNotIn(token, SESSIONS)

    def test_unknown_token_does_not_create_session_state(self):
        before = set(SESSIONS)
        status, _, _ = self.request("GET", "/results?token=does-not-exist")
        self.assertEqual(status, 404)
        self.assertEqual(set(SESSIONS), before)


if __name__ == "__main__":
    unittest.main()
