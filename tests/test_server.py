from __future__ import annotations

import http.client
import re
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from server import Handler, SESSIONS, ThreadingHTTPServer


class ServerTests(unittest.TestCase):
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

    def test_home_sample_audit_and_exports(self):
        status, _, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Local, deterministic", body)
        status, _, body = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        token = re.search(rb"name='token' value='([^']+)'", body).group(1).decode()
        mappings = {"token": token}
        for field, header in {"description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate", "amount": "Amount", "category": "Category", "markup_pct": "Markup %", "margin_pct": "Margin %"}.items():
            mappings[f"map__synthetic_civil_estimate__{field}"] = header
        encoded = urlencode(mappings).encode()
        status, _, body = self.request("POST", "/audit", encoded, {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded))})
        self.assertEqual(status, 200)
        self.assertIn(b"Review-status score", body)
        status, headers, csv_data = self.request("GET", f"/export/findings?token={token}")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn(b"R011", csv_data)
        status, _, html_data = self.request("GET", f"/export/summary?token={token}")
        self.assertEqual(status, 200)
        self.assertIn(b"Required human review", html_data)

    def test_uploaded_csv_and_repeated_sessions(self):
        boundary = "----local-audit-boundary"
        payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"estimate\"; filename=\"simple.csv\"\r\nContent-Type: text/csv\r\n\r\nDescription,Quantity,Unit,Rate,Amount\nPipe,2,EA,10,20\n\r\n--{boundary}--\r\n").encode()
        headers = {"Content-Type": f'multipart/form-data; boundary="{boundary}"', "Content-Length": str(len(payload))}
        status, _, body = self.request("POST", "/prepare", payload, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Sheet: simple", body)
        second_status, _, second_body = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(second_status, 200)
        self.assertIn(b"Sheet: synthetic_civil_estimate", second_body)

    def test_malformed_multipart_returns_safe_error(self):
        payload = b"not a multipart payload"
        status, _, body = self.request("POST", "/prepare", payload, {"Content-Type": "text/plain", "Content-Length": str(len(payload))})
        self.assertEqual(status, 400)
        self.assertIn(b"multipart form data", body)

    def test_cover_sheet_can_be_excluded(self):
        token = "cover-sheet-test"
        SESSIONS[token] = {"filename": "book.xlsx", "created": time.monotonic(), "sheets": {
            "Cover": [{"Title": "Synthetic bid cover", "__source_row": "1"}],
            "Estimate": [{"Description": "Pipe", "Quantity": "2", "Unit": "EA", "Rate": "10", "Amount": "20", "__source_row": "2"}],
        }}
        form = urlencode({
            "token": token, "include__Estimate": "1", "map__Estimate__description": "Description", "map__Estimate__quantity": "Quantity", "map__Estimate__unit": "Unit", "map__Estimate__rate": "Rate", "map__Estimate__amount": "Amount",
        }).encode()
        status, _, body = self.request("POST", "/audit", form, {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(form))})
        self.assertEqual(status, 200)
        self.assertIn(b"Rows reviewed:</strong> 1", body)

    def test_expired_export_returns_safe_error(self):
        status, _, body = self.request("GET", "/export/findings?token=not-a-session")
        self.assertEqual(status, 404)
        self.assertIn(b"no longer available", body)


if __name__ == "__main__":
    unittest.main()
