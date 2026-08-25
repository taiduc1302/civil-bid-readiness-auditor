from __future__ import annotations

import csv
import hashlib
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from server import Handler, ThreadingHTTPServer


class ServerReferenceMetadataTests(unittest.TestCase):
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

    def multipart(self, files=None, texts=None):
        boundary = "----reference-metadata-boundary"
        chunks: list[bytes] = []
        for name, (filename, payload) in (files or {}).items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
            chunks.append(b"Content-Type: text/csv\r\n\r\n")
            chunks.append(payload)
            chunks.append(b"\r\n")
        for name, value in (texts or {}).items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n'.encode())
            chunks.append(b"Content-Type: text/plain; charset=utf-8\r\n\r\n")
            chunks.append(str(value).encode("utf-8"))
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        return body, {"Content-Type": f'multipart/form-data; boundary="{boundary}"', "Content-Length": str(len(body))}

    def audited_heavybid_fixture(self):
        path = ROOT / "samples" / "synthetic_heavybid_style_resource_export.csv"
        body, headers = self.multipart(files={"estimate": (path.name, path.read_bytes())})
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
            "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded)),
        })
        self.assertEqual(status, 200)
        return token

    def upload_resource_reference(self, token, revision="Approved snapshot R3", payload=None):
        reference = ROOT / "samples" / "synthetic_resource_reference.csv"
        data = reference.read_bytes() if payload is None else payload
        body, headers = self.multipart(
            files={"resource_reference": (reference.name, data)},
            texts={"resource_revision": revision},
        )
        return data, self.request("POST", f"/references?token={token}", body, headers)

    def test_metadata_is_visible_and_exported_with_exact_sha(self):
        token = self.audited_heavybid_fixture()
        data, (status, _, page) = self.upload_resource_reference(token)
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(status, 200)
        self.assertIn(b"Reference evidence metadata", page)
        self.assertIn(b"Approved snapshot R3", page)
        self.assertIn(digest.encode(), page)
        self.assertIn(b"NOT_ESTABLISHED_BY_APP", page)

        status, _, exported = self.request("GET", f"/export/references?token={token}")
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8"))))
        resource_rows = [row for row in rows if row["reference_type"] == "resource"]
        self.assertTrue(resource_rows)
        self.assertTrue(all(row["reference_filename"] == "synthetic_resource_reference.csv" for row in resource_rows))
        self.assertTrue(all(row["reference_revision"] == "Approved snapshot R3" for row in resource_rows))
        self.assertTrue(all(row["reference_sha256"] == digest for row in resource_rows))
        self.assertTrue(all(row["authority_status"] == "NOT_ESTABLISHED_BY_APP" for row in resource_rows))
        self.assertTrue(any(row["sheet"] == "synthetic_heavybid_style_resource_export" for row in resource_rows))

    def test_review_package_manifest_and_reference_csv_include_metadata(self):
        token = self.audited_heavybid_fixture()
        data, (status, _, _) = self.upload_resource_reference(token, revision="Issued 2026-08-25")
        self.assertEqual(status, 200)
        digest = hashlib.sha256(data).hexdigest()

        status, _, package = self.request("GET", f"/export/package?token={token}")
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(package)) as book:
            manifest = json.loads(book.read("manifest.json"))
            self.assertTrue(manifest["contents"]["reference_metadata_included"])
            self.assertFalse(manifest["safety"]["reference_authority_established_by_app"])
            self.assertEqual(manifest["reference_metadata"][0]["revision"], "Issued 2026-08-25")
            self.assertEqual(manifest["reference_metadata"][0]["sha256"], digest)
            rows = list(csv.DictReader(io.StringIO(book.read("references.csv").decode("utf-8"))))
            self.assertTrue(any(row["reference_sha256"] == digest for row in rows))

    def test_blank_revision_remains_blank(self):
        token = self.audited_heavybid_fixture()
        _, (status, _, _) = self.upload_resource_reference(token, revision="")
        self.assertEqual(status, 200)
        status, _, exported = self.request("GET", f"/export/references?token={token}")
        rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8"))))
        self.assertTrue(rows)
        self.assertTrue(all(row["reference_revision"] == "" for row in rows))

    def test_failed_rerun_does_not_replace_previous_metadata(self):
        token = self.audited_heavybid_fixture()
        _, (status, _, _) = self.upload_resource_reference(token, revision="Good snapshot")
        self.assertEqual(status, 200)

        duplicate = b"resource_code,description,unit\nDUP,One,EA\ndup,Two,EA\n"
        _, (status, _, body) = self.upload_resource_reference(token, revision="Bad replacement", payload=duplicate)
        self.assertEqual(status, 400)
        self.assertIn(b"Duplicate reference code", body)

        status, _, exported = self.request("GET", f"/export/references?token={token}")
        rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8"))))
        self.assertTrue(rows)
        self.assertTrue(all(row["reference_revision"] == "Good snapshot" for row in rows))


if __name__ == "__main__":
    unittest.main()
