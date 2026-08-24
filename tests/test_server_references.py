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


class ServerReferenceTests(unittest.TestCase):
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

    def multipart(self, fields: dict[str, tuple[str, bytes]]):
        boundary = "----reference-boundary"
        chunks: list[bytes] = []
        for name, (filename, payload) in fields.items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
            chunks.append(b"Content-Type: text/csv\r\n\r\n")
            chunks.append(payload)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        return body, {"Content-Type": f'multipart/form-data; boundary="{boundary}"', "Content-Length": str(len(body))}

    def audited_heavybid_fixture(self):
        path = ROOT / "samples" / "synthetic_heavybid_style_resource_export.csv"
        body, headers = self.multipart({"estimate": (path.name, path.read_bytes())})
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
        status, _, page = self.request("POST", "/audit", encoded, {
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded)),
        })
        self.assertEqual(status, 200)
        self.assertIn(b"Governed reference validation", page)
        self.assertIn(f"/references?token={token}".encode(), page)
        return token

    def test_explicit_resource_reference_can_be_uploaded_and_exported(self):
        token = self.audited_heavybid_fixture()
        reference = ROOT / "samples" / "synthetic_resource_reference.csv"
        body, headers = self.multipart({"resource_reference": (reference.name, reference.read_bytes())})
        status, _, page = self.request("POST", f"/references?token={token}", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Governed reference validation completed", page)
        self.assertIn(b"synthetic_resource_reference.csv", page)
        self.assertIn(b"NO_MATCH", page)

        status, response_headers, data = self.request("GET", f"/export/references?token={token}")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", response_headers["Content-Type"])
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        self.assertTrue(any(row["status"] == "MATCH" for row in rows))
        self.assertTrue(any(row["status"] == "NO_MATCH" for row in rows))

    def test_reference_upload_rejects_missing_file(self):
        token = self.audited_heavybid_fixture()
        boundary = "----empty-ref"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="resource_reference"; filename=""\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
            "\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        status, _, page = self.request("POST", f"/references?token={token}", body, {
            "Content-Type": f'multipart/form-data; boundary="{boundary}"', "Content-Length": str(len(body)),
        })
        self.assertEqual(status, 400)
        self.assertIn(b"Choose at least one Activity or Resource reference CSV", page)

    def test_reference_requires_corresponding_mapped_field(self):
        status, _, page = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        token = re.search(rb"name='token' value='([^']+)'", page).group(1).decode()
        mappings = {"token": token}
        for field, header in {"description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate"}.items():
            mappings[f"map__synthetic_civil_estimate__{field}"] = header
        encoded = urlencode(mappings).encode()
        status, _, _ = self.request("POST", "/audit", encoded, {
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded)),
        })
        self.assertEqual(status, 200)

        reference = ROOT / "samples" / "synthetic_resource_reference.csv"
        body, headers = self.multipart({"resource_reference": (reference.name, reference.read_bytes())})
        status, _, page = self.request("POST", f"/references?token={token}", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"no Resource Code field is mapped", page)


if __name__ == "__main__":
    unittest.main()
