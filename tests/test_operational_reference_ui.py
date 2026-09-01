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

from server import Handler, SESSIONS, ThreadingHTTPServer


_SOURCE = (
    "Bid Item,Activity Code,Resource Type,Resource Code,Resource Description,Quantity,Unit,Rate,Crew Code,Production Rate\n"
    "100,EXC,Equipment,EQ-EXC,Excavate,10,BCY,100,CR-EARTH,12\n"
    "200,STM300,Labour,L-PIPE,Install pipe,20,M,50,OTHER-CREW,5\n"
    "300,UNKNOWN,Equipment,EQ-X,Unknown activity,1,HR,75,CR-X,1\n"
).encode()

_OPERATIONAL_REFERENCE = (
    "activity_code,crew_code,production_rate,historical_cost\n"
    "EXC,CR-EARTH,12,999\n"
    "STM300,CR-PIPE,5,888\n"
).encode()


class OperationalReferenceUiTests(unittest.TestCase):
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

    def multipart(self, files=None, fields=None):
        boundary = "----operational-reference-boundary"
        chunks: list[bytes] = []
        for name, value in (fields or {}).items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            chunks.append(str(value).encode())
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

    def audited_operational_source(self, include_production=True):
        body, headers = self.multipart(files={"estimate": ("operational_export.csv", _SOURCE)})
        status, _, mapping = self.request("POST", "/prepare", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"map__operational_export__crew_code", mapping)
        self.assertIn(b"map__operational_export__production_rate", mapping)
        self.assertIn(b"value='Crew Code' selected", mapping)
        self.assertIn(b"value='Production Rate' selected", mapping)
        token = re.search(rb"name='token' value='([^']+)'", mapping).group(1).decode()

        mappings = {"token": token, "include__operational_export": "1"}
        field_map = {
            "description": "Resource Description",
            "quantity": "Quantity",
            "unit": "Unit",
            "rate": "Rate",
            "bid_item": "Bid Item",
            "activity": "Activity Code",
            "resource_type": "Resource Type",
            "resource_code": "Resource Code",
            "crew_code": "Crew Code",
        }
        if include_production:
            field_map["production_rate"] = "Production Rate"
        for field, header in field_map.items():
            mappings[f"map__operational_export__{field}"] = header
        encoded = urlencode(mappings).encode()
        status, _, results = self.request(
            "POST",
            "/audit",
            encoded,
            {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded))},
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Operational Activity evidence", results)
        self.assertIn(b"name='operational_reference'", results)
        self.assertIn(b"temporary-session UI evidence only", results)
        return token, results

    def upload_operational_reference(self, token, payload=_OPERATIONAL_REFERENCE):
        body, headers = self.multipart(
            files={"operational_reference": ("operational_activity_reference.csv", payload)},
            fields={"operational_revision": "Training Rev B"},
        )
        return self.request("POST", f"/references?token={token}", body, headers)

    def test_explicit_operational_evidence_is_row_linked_and_session_only(self):
        token, _ = self.audited_operational_source()
        status, _, page = self.upload_operational_reference(token)
        self.assertEqual(status, 200)
        self.assertIn(b"Operational Activity evidence", page)
        self.assertIn(b"MATCH", page)
        self.assertIn(b"CREW_MISMATCH", page)
        self.assertIn(b"NO_MATCH", page)
        self.assertIn(b"operational_activity_reference.csv", page)
        self.assertIn(b"Training Rev B", page)
        self.assertIn(hashlib.sha256(_OPERATIONAL_REFERENCE).hexdigest().encode(), page)
        self.assertIn(b"NOT_ESTABLISHED_BY_APP", page)
        self.assertIn(b"not included in review-package v1", page)

        session = SESSIONS[token]
        statuses = [item["status"] for item in session["operational_reference_results"]]
        self.assertEqual(statuses, ["MATCH", "CREW_MISMATCH", "NO_MATCH"])
        self.assertEqual([item["source_row"] for item in session["operational_reference_results"]], [2, 3, 4])
        self.assertTrue(all(item["sheet"] == "operational_export" for item in session["operational_reference_results"]))
        self.assertEqual(session["operational_reference_metadata"]["authority_status"], "NOT_ESTABLISHED_BY_APP")

        status, response_headers, package = self.request("GET", f"/export/package?token={token}")
        self.assertEqual(status, 200)
        self.assertIn("application/zip", response_headers["Content-Type"])
        with zipfile.ZipFile(io.BytesIO(package)) as book:
            self.assertNotIn("references.csv", book.namelist())
            manifest = json.loads(book.read("manifest.json"))
        self.assertEqual(manifest["reference_metadata"], [])
        self.assertEqual(manifest["reference_status_counts"], {})
        self.assertNotIn("operational_reference_results", manifest)

        status, _, regular_csv = self.request("GET", f"/export/references?token={token}")
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(regular_csv.decode("utf-8"))))
        self.assertEqual(rows, [])

    def test_operational_upload_requires_explicit_source_mapping_and_overlap(self):
        status, _, mapping = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        token = re.search(rb"name='token' value='([^']+)'", mapping).group(1).decode()
        form = {"token": token}
        for field, header in {"description": "Description", "quantity": "Quantity", "unit": "Unit", "rate": "Rate"}.items():
            form[f"map__synthetic_civil_estimate__{field}"] = header
        encoded = urlencode(form).encode()
        status, _, results = self.request(
            "POST", "/audit", encoded,
            {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded))},
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Not available for this audit", results)
        self.assertNotIn(b"name='operational_reference'", results)

        status, _, error = self.upload_operational_reference(token)
        self.assertEqual(status, 400)
        self.assertIn(b"requires Activity plus Crew Code and/or Production Rate", error)

        token, _ = self.audited_operational_source(include_production=False)
        prod_only = b"activity_code,production_rate\nEXC,12\nSTM300,5\n"
        status, _, error = self.upload_operational_reference(token, prod_only)
        self.assertEqual(status, 400)
        self.assertIn(b"no Crew Code / Production Rate field that overlaps", error)

    def test_successful_reaudit_clears_stale_operational_evidence(self):
        token, _ = self.audited_operational_source(include_production=True)
        status, _, _ = self.upload_operational_reference(token)
        self.assertEqual(status, 200)
        self.assertIn("operational_reference_results", SESSIONS[token])

        mappings = {"token": token, "include__operational_export": "1"}
        for field, header in {
            "description": "Resource Description",
            "quantity": "Quantity",
            "unit": "Unit",
            "rate": "Rate",
            "bid_item": "Bid Item",
            "activity": "Activity Code",
            "resource_type": "Resource Type",
            "resource_code": "Resource Code",
            "crew_code": "Crew Code",
        }.items():
            mappings[f"map__operational_export__{field}"] = header
        encoded = urlencode(mappings).encode()
        status, _, page = self.request(
            "POST", "/audit", encoded,
            {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded))},
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Previous operational evidence was cleared", page)
        self.assertNotIn("operational_reference_results", SESSIONS[token])
        self.assertIn(b"This audit explicitly maps <strong>Crew Code</strong>", page)


if __name__ == "__main__":
    unittest.main()
