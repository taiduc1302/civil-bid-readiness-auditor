from __future__ import annotations

import copy
import hashlib
import http.client
import io
import json
import sys
import threading
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_delta import compare_review_packages
from review_delta_export import (
    build_review_delta_export,
    delta_export_integrity,
    verify_review_delta_export,
)
from review_package import build_review_package
from server import Handler, SESSIONS, ThreadingHTTPServer


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


class ReviewDeltaVerificationTests(unittest.TestCase):
    def session(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }

    def bundle(self, earlier_name="earlier.zip", later_name="later.zip"):
        earlier = self.session()
        later = copy.deepcopy(earlier)
        later["dispositions"][1] = {"status": "Reviewed", "reason": "Checked."}
        earlier_package = build_review_package(earlier)[0]
        later_package = build_review_package(later)[0]
        result = compare_review_packages(earlier_name, earlier_package, later_name, later_package)
        return build_review_delta_export(result)[0]

    def members(self, data):
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            return {name: book.read(name) for name in book.namelist() if not name.endswith("/")}

    def rehash(self, members):
        members = dict(members)
        members.pop("integrity.json", None)
        members["integrity.json"] = _json_bytes(delta_export_integrity(members))
        return members

    def make_zip(self, members, *, directory=None, duplicate=None):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as book:
            for name, payload in members.items():
                book.writestr(name, payload)
            if directory:
                book.writestr(directory.rstrip("/") + "/", b"")
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    book.writestr(duplicate, members[duplicate])
        return output.getvalue()

    def test_generated_bundle_verifies_with_bounded_preview_and_safety_flags(self):
        verified = verify_review_delta_export(self.bundle())
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["export_format"], "civil-estimate-review-delta-export")
        self.assertEqual(verified["export_version"], 1)
        self.assertEqual(verified["members_verified"], 6)
        self.assertEqual(verified["finding_counts"]["REVIEW_CHANGED"], 1)
        self.assertEqual(len(verified["preview"]["finding_changes"]), 1)
        self.assertFalse(verified["session_created"])
        self.assertFalse(verified["re_audit_performed"])
        self.assertFalse(verified["correctness_inferred"])
        self.assertFalse(verified["readiness_inferred"])
        self.assertFalse(verified["heavybid_import_validated"])

    def test_changed_member_fails_hash_before_semantic_validation(self):
        members = self.members(self.bundle())
        members["README.txt"] = b"X" + members["README.txt"][1:]
        with self.assertRaisesRegex(ValueError, "SHA-256 does not match"):
            verify_review_delta_export(self.make_zip(members))

    def test_rehashed_relaxed_safety_and_manifest_drift_fail_semantically(self):
        members = self.members(self.bundle())
        comparison = json.loads(members["review_delta.json"])
        comparison["correctness_inferred"] = True
        members["review_delta.json"] = _json_bytes(comparison)
        with self.assertRaisesRegex(ValueError, "correctness_inferred"):
            verify_review_delta_export(self.make_zip(self.rehash(members)))

        members = self.members(self.bundle())
        manifest = json.loads(members["manifest.json"])
        manifest["safety"]["readiness_inferred"] = True
        members["manifest.json"] = _json_bytes(manifest)
        with self.assertRaisesRegex(ValueError, "manifest does not match"):
            verify_review_delta_export(self.make_zip(self.rehash(members)))

    def test_rehashed_csv_drift_fails_against_canonical_json(self):
        members = self.members(self.bundle())
        members["finding_changes.csv"] += b"EXTRA,ROW\r\n"
        with self.assertRaisesRegex(ValueError, "finding_changes.csv does not match"):
            verify_review_delta_export(self.make_zip(self.rehash(members)))

    def test_directory_unsafe_duplicate_and_unexpected_members_fail_closed(self):
        members = self.members(self.bundle())
        with self.assertRaisesRegex(ValueError, "directory entry"):
            verify_review_delta_export(self.make_zip(members, directory="extra"))

        unsafe = dict(members)
        unsafe["../outside.txt"] = b"x"
        with self.assertRaisesRegex(ValueError, "unsafe member path"):
            verify_review_delta_export(self.make_zip(unsafe))

        with self.assertRaisesRegex(ValueError, "duplicate member names"):
            verify_review_delta_export(self.make_zip(members, duplicate="manifest.json"))

        unexpected = dict(members)
        unexpected["extra.txt"] = b"x"
        with self.assertRaisesRegex(ValueError, "unexpected members"):
            verify_review_delta_export(self.make_zip(unexpected))

    def test_blank_nonzip_and_unsupported_identity_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "blank"):
            verify_review_delta_export(b"")
        with self.assertRaisesRegex(ValueError, "readable ZIP"):
            verify_review_delta_export(b"not-a-zip")

        members = self.members(self.bundle())
        manifest = json.loads(members["manifest.json"])
        manifest["export_format"] = "other-format"
        members["manifest.json"] = _json_bytes(manifest)
        with self.assertRaisesRegex(ValueError, "manifest identity"):
            verify_review_delta_export(self.make_zip(self.rehash(members)))


class ReviewDeltaVerificationHttpTests(unittest.TestCase):
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

    def bundle(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        earlier = {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }
        later = copy.deepcopy(earlier)
        later["dispositions"][1] = {"status": "Reviewed", "reason": "Checked."}
        comparison = compare_review_packages(
            "<script>alert(1)</script>.zip",
            build_review_package(earlier)[0],
            "later.zip",
            build_review_package(later)[0],
        )
        return build_review_delta_export(comparison)[0]

    def multipart(self, payload):
        boundary = "----review-delta-verification-boundary"
        body = (
            f"--{boundary}\r\n".encode()
            + b'Content-Disposition: form-data; name="delta_export"; filename="delta.zip"\r\n'
            + b"Content-Type: application/zip\r\n\r\n"
            + payload
            + b"\r\n"
            + f"--{boundary}--\r\n".encode()
        )
        return body, {
            "Content-Type": f'multipart/form-data; boundary="{boundary}"',
            "Content-Length": str(len(body)),
        }

    def test_home_and_verification_page_are_available_without_session(self):
        status, _, home = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Verify Review Delta evidence", home)
        self.assertIn(b"href='/verify-review-delta'", home)

        status, _, page = self.request("GET", "/verify-review-delta")
        self.assertEqual(status, 200)
        self.assertIn(b"Review Delta evidence ZIP", page)
        self.assertEqual(SESSIONS, {})

    def test_valid_bundle_verifies_with_escaped_bounded_preview_and_no_session(self):
        body, headers = self.multipart(self.bundle())
        status, _, page = self.request("POST", "/verify-review-delta", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Review Delta export verified", page)
        self.assertIn(b"Integrity and internal consistency only", page)
        self.assertIn(b"REVIEW_CHANGED", page)
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;.zip", page)
        self.assertNotIn(b"<script>alert(1)</script>.zip", page)
        self.assertEqual(SESSIONS, {})

    def test_invalid_bundle_returns_safe_error_and_no_session(self):
        body, headers = self.multipart(b"not-a-zip")
        status, response_headers, page = self.request("POST", "/verify-review-delta", body, headers)
        self.assertEqual(status, 400)
        self.assertIn("text/html", response_headers["Content-Type"])
        self.assertIn(b"Verification failed", page)
        self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
