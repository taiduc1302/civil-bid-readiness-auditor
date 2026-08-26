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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from server import Handler, ThreadingHTTPServer


class ServerReferenceViewTests(unittest.TestCase):
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

    def multipart(self, files=None, fields=None):
        boundary = "----reference-view-boundary"
        chunks: list[bytes] = []
        for name, value in (fields or {}).items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            chunks.append(str(value).encode("utf-8"))
            chunks.append(b"\r\n")
        for name, (filename, payload) in (files or {}).items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
            chunks.append(b"Content-Type: text/csv\r\n\r\n")
            chunks.append(payload)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        return body, {
            "Content-Type": f'multipart/form-data; boundary="{boundary}"',
            "Content-Length": str(len(body)),
        }

    def audited_with_resource_reference(self):
        estimate = ROOT / "samples" / "synthetic_heavybid_style_resource_export.csv"
        body, headers = self.multipart(files={"estimate": (estimate.name, estimate.read_bytes())})
        status, _, page = self.request("POST", "/prepare", body, headers)
        self.assertEqual(status, 200)
        token = re.search(rb"name='token' value='([^']+)'", page).group(1).decode()

        mappings = {"token": token, "include__synthetic_heavybid_style_resource_export": "1"}
        for field, header in {
            "description": "Resource Description",
            "quantity": "Quantity",
            "unit": "Unit",
            "rate": "Rate",
            "amount": "Amount",
            "category": "Category",
            "bid_item": "Bid Item",
            "activity": "Activity Code",
            "resource_type": "Resource Type",
            "resource_code": "Resource Code",
        }.items():
            mappings[f"map__synthetic_heavybid_style_resource_export__{field}"] = header
        encoded = urlencode(mappings).encode()
        status, _, _ = self.request("POST", "/audit", encoded, {
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(encoded)),
        })
        self.assertEqual(status, 200)

        reference = ROOT / "samples" / "synthetic_resource_reference.csv"
        body, headers = self.multipart(
            files={"resource_reference": (reference.name, reference.read_bytes())},
            fields={"resource_revision": "Training Rev B"},
        )
        status, _, page = self.request("POST", f"/references?token={token}", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Training Rev B", page)
        return token, page

    def test_default_reference_view_shows_exceptions_only(self):
        token, page = self.audited_with_resource_reference()
        match = re.search(rb"Visible:</strong> (\d+) of (\d+) checks", page)
        self.assertIsNotNone(match)
        visible, total = map(int, match.groups())
        self.assertGreater(visible, 0)
        self.assertLess(visible, total)
        self.assertIn(b"name='ref_status'", page)
        self.assertIn(b"value='Exceptions' selected", page)
        self.assertNotIn(b"<td class='MATCH'>", page)

        status, _, filtered = self.request("GET", f"/results?token={token}&ref_status=NO_MATCH")
        self.assertEqual(status, 200)
        self.assertIn(b"value='NO_MATCH' selected", filtered)
        self.assertIn(b"<td class='NO_MATCH'>", filtered)
        self.assertNotIn(b"<td class='UNIT_MISMATCH'>", filtered)

    def test_reference_view_composes_with_findings_view(self):
        token, _ = self.audited_with_resource_reference()
        status, _, page = self.request(
            "GET",
            f"/results?token={token}&severity=Priority&sort_by=rule&group_by=rule&ref_status=All&ref_sort=code&ref_group=type",
        )
        self.assertEqual(status, 200)
        self.assertIn(b"name='severity'", page)
        self.assertIn(b"value='Priority' selected", page)
        self.assertIn(b"name='ref_sort'", page)
        self.assertIn(b"value='code' selected", page)
        self.assertIn(b"name='ref_group'", page)
        self.assertIn(b"value='type' selected", page)
        self.assertIn(b"name='ref_status' value='All'", page)
        self.assertIn(b"name='ref_sort' value='code'", page)
        self.assertIn(b"severity=Priority", page)
        self.assertGreater(page.count(b"class='group-row'"), 1)

    def test_reference_search_uses_metadata_and_invalid_params_fail_safe(self):
        token, _ = self.audited_with_resource_reference()
        query = urlencode({"token": token, "ref_status": "All", "ref_q": "Training Rev B"})
        status, _, page = self.request("GET", f"/results?{query}")
        self.assertEqual(status, 200)
        match = re.search(rb"Visible:</strong> (\d+) of (\d+) checks", page)
        self.assertIsNotNone(match)
        visible, total = map(int, match.groups())
        self.assertEqual(visible, total)
        self.assertIn(b"Training Rev B", page)

        status, _, page = self.request(
            "GET",
            f"/results?token={token}&ref_status=bad&ref_type=bad&ref_sort=bad&ref_group=bad",
        )
        self.assertEqual(status, 200)
        match = re.search(rb"Visible:</strong> (\d+) of (\d+) checks", page)
        self.assertIsNotNone(match)
        visible, total = map(int, match.groups())
        self.assertGreater(visible, 0)
        self.assertLess(visible, total)
        self.assertNotIn(b"<td class='MATCH'>", page)

    def test_reference_export_remains_full_session_export(self):
        token, _ = self.audited_with_resource_reference()
        status, _, _ = self.request("GET", f"/results?token={token}&ref_status=NO_MATCH")
        self.assertEqual(status, 200)

        status, headers, data = self.request("GET", f"/export/references?token={token}")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        statuses = {row["status"] for row in rows}
        self.assertIn("MATCH", statuses)
        self.assertIn("NO_MATCH", statuses)


if __name__ == "__main__":
    unittest.main()
