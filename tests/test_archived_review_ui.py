from __future__ import annotations

import copy
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

from archived_review import ARCHIVED_REVIEW_SESSION_MODE, build_archived_review_session
from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_package import build_review_package, verify_review_package
from server import Handler, SESSIONS, ThreadingHTTPServer, findings_page


class ArchivedReviewUiTests(unittest.TestCase):
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
            {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(encoded))},
        )

    def package(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return build_review_package({
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        })

    def multipart(self, filename: str, payload: bytes, acknowledged: bool):
        boundary = "----archived-review-continuation"
        chunks: list[bytes] = []
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="review_package"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: application/zip\r\n\r\n",
            payload,
            b"\r\n",
        ])
        if acknowledged:
            chunks.extend([
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="archived_review_ack"\r\n\r\n',
                b"yes\r\n",
            ])
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        return body, {
            "Content-Type": f'multipart/form-data; boundary="{boundary}"',
            "Content-Length": str(len(body)),
        }

    def open_archived_review(self):
        package, filename = self.package()
        body, headers = self.multipart(filename, package, True)
        status, _, page = self.request("POST", "/continue-review-package", body, headers)
        self.assertEqual(status, 200)
        token_match = re.search(rb"name='token' value='([^']+)'", page)
        self.assertIsNotNone(token_match)
        return token_match.group(1).decode(), page, package, filename

    def test_get_contract_and_verifier_link_are_explicitly_not_reaudit(self):
        status, _, page = self.request("GET", "/continue-review-package")
        self.assertEqual(status, 200)
        self.assertIn(b"Review-package re-open contract", page)
        self.assertIn(b"Verify package", page)
        self.assertIn(b"Continue archived human review", page)
        self.assertIn(b"True estimate re-audit", page)
        self.assertIn(b"not a restorable estimate-audit workspace", page)
        self.assertIn(b"original estimate and reference file bytes", page)
        self.assertIn(b"archived_review_ack", page)
        self.assertIn(b"Start a new source-backed audit", page)

        package, filename = self.package()
        boundary = "----verify-archived-link"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"review_package\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/zip\r\n\r\n"
        ).encode() + package + f"\r\n--{boundary}--\r\n".encode()
        status, _, verified = self.request("POST", "/verify-package", body, {
            "Content-Type": f'multipart/form-data; boundary="{boundary}"',
            "Content-Length": str(len(body)),
        })
        self.assertEqual(status, 200)
        self.assertIn(b"Open archived review continuation", verified)
        self.assertIn(b"not restoration or re-audit", verified)
        self.assertEqual(SESSIONS, {})

    def test_acknowledgement_is_required_before_session_creation(self):
        package, filename = self.package()
        body, headers = self.multipart(filename, package, False)
        status, _, page = self.request("POST", "/continue-review-package", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"Explicit acknowledgement is required", page)
        self.assertEqual(SESSIONS, {})

    def test_archived_session_supports_human_review_but_not_audit_or_reference_rerun(self):
        token, page, package, filename = self.open_archived_review()
        session = SESSIONS[token]
        expected_hash = hashlib.sha256(package).hexdigest().encode()
        self.assertEqual(session["session_mode"], ARCHIVED_REVIEW_SESSION_MODE)
        self.assertNotIn("audit_sheets", session)
        self.assertEqual(session["sheets"], {})
        self.assertIn(b"Archived review snapshot", page)
        self.assertIn(b"Archived review snapshot \xe2\x80\x94 continuation only", page)
        self.assertIn(b"not a restored or re-audited estimate", page)
        self.assertIn(filename.encode(), page)
        self.assertIn(expected_hash, page)
        self.assertIn(b"human finding dispositions and notes only", page)
        self.assertIn(b"Start a new source-backed audit", page)
        self.assertIn(b"No estimate re-audit", page)
        self.assertIn(b"Select for bulk", page)
        self.assertIn(b"Archived reference evidence only", page)
        self.assertNotIn(b"Validate against supplied references", page)

        status, _, filtered = self.request("GET", f"/results?token={token}&severity=High")
        self.assertEqual(status, 200)
        self.assertIn(b"Archived review snapshot \xe2\x80\x94 continuation only", filtered)
        self.assertIn(filename.encode(), filtered)
        self.assertIn(expected_hash, filtered)
        self.assertIn(b"True re-audit requires", filtered)

        status, _, reviewed = self.post_form("/review", [
            ("token", token),
            ("status__1", "Reviewed"),
            ("reason__1", "Continued from archived snapshot"),
        ])
        self.assertEqual(status, 200)
        self.assertIn(b"Review states saved", reviewed)
        self.assertIn(b"Archived review snapshot \xe2\x80\x94 continuation only", reviewed)
        self.assertIn(filename.encode(), reviewed)
        self.assertIn(expected_hash, reviewed)
        self.assertEqual(SESSIONS[token]["dispositions"][1]["status"], "Reviewed")

        before_result = copy.deepcopy(SESSIONS[token]["result"])
        status, _, audit_page = self.post_form("/audit", [("token", token)])
        self.assertEqual(status, 400)
        self.assertIn(b"Select at least one sheet", audit_page)
        self.assertEqual(SESSIONS[token]["result"], before_result)

        status, _, reference_page = self.request(
            "POST",
            f"/references?token={token}",
            b"",
            {"Content-Length": "0"},
        )
        self.assertEqual(status, 400)
        self.assertIn(b"temporary audit session expired", reference_page)
        self.assertEqual(SESSIONS[token]["result"], before_result)

    def test_normal_audit_result_does_not_show_archived_provenance_contract(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        session = {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }
        page = findings_page("live-token", session)
        self.assertNotIn(b"archived-provenance", page)
        self.assertNotIn(b"Archived review snapshot \xe2\x80\x94 continuation only", page)
        self.assertIn(b"Start another audit", page)

    def test_reexported_package_records_snapshot_derived_provenance_and_can_be_reopened(self):
        token, _, _, source_name = self.open_archived_review()
        status, headers, package = self.request("GET", f"/export/package?token={token}")
        self.assertEqual(status, 200)
        self.assertIn("application/zip", headers["Content-Type"])
        verify_review_package(package)
        with zipfile.ZipFile(io.BytesIO(package), "r") as book:
            manifest = json.loads(book.read("manifest.json").decode("utf-8"))
        context = manifest["session_context"]
        self.assertEqual(context["mode"], ARCHIVED_REVIEW_SESSION_MODE)
        self.assertTrue(context["continuation_only"])
        self.assertFalse(context["re_audit_performed"])
        self.assertFalse(context["original_estimate_bytes_available"])
        self.assertFalse(context["reference_rerun_available"])
        self.assertEqual(context["source_package_filename"], source_name)
        self.assertEqual(len(context["source_package_sha256"]), 64)

        reopened = build_archived_review_session("second-generation.zip", package)
        self.assertEqual(reopened["archived_snapshot_origin"]["source_session_mode"], ARCHIVED_REVIEW_SESSION_MODE)
        self.assertNotIn("package_bytes", reopened)
        self.assertNotIn("audit_sheets", reopened)


if __name__ == "__main__":
    unittest.main()
