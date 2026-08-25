from __future__ import annotations

import http.client
import io
import json
import re
import sys
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from server import Handler, ThreadingHTTPServer


class ServerPackageTests(unittest.TestCase):
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
        self.assertIn(b"Download review package ZIP", body)
        return token

    def test_package_endpoint_returns_review_zip(self):
        token = self.audited_sample()
        status, headers, data = self.request("GET", f"/export/package?token={token}")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/zip")
        self.assertIn("review_package_v1.zip", headers["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            self.assertIn("manifest.json", book.namelist())
            self.assertIn("findings.csv", book.namelist())
            self.assertIn("review.csv", book.namelist())
            manifest = json.loads(book.read("manifest.json"))
            self.assertEqual(manifest["source_filename"], "synthetic_civil_estimate.csv")
            self.assertFalse(manifest["safety"]["HEAVYBID_IMPORT_VALIDATED"])

    def test_missing_package_session_returns_safe_error(self):
        status, _, body = self.request("GET", "/export/package?token=missing")
        self.assertEqual(status, 404)
        self.assertIn(b"no longer available", body)


if __name__ == "__main__":
    unittest.main()
