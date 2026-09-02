from __future__ import annotations

import copy
import http.client
import io
import re
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import InputError, audit, parse_upload
from finding_review import default_dispositions
from review_delta import compare_review_packages
from review_delta_export import MAX_DELTA_EXPORT_BYTES, build_review_delta_export
from review_package import build_review_package
from review_timeline_ui import (
    MAX_TIMELINE_DETAIL_CELL_CHARS,
    TIMELINE_MAX_REQUEST_BYTES,
    _cell,
    _timeline_multipart_message,
)
from server import Handler, SESSIONS, ThreadingHTTPServer


class ReviewTimelineUiTests(unittest.TestCase):
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

    def base_session(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }

    def packages(self):
        a = self.base_session()
        b = copy.deepcopy(a)
        c = copy.deepcopy(a)
        d = copy.deepcopy(a)
        b["dispositions"][1] = {"status": "Reviewed", "reason": "<evil&review>"}
        c["dispositions"][1] = {"status": "Reviewed", "reason": "<evil&review>"}
        c["dispositions"][2] = {"status": "Needs correction", "reason": "B to C"}
        d["dispositions"][3] = {"status": "Accepted", "reason": "D"}
        return tuple(build_review_package(item)[0] for item in (a, b, c, d))

    def long_chain_packages(self):
        base = self.base_session()
        snapshots = [base]
        for index in range(1, 11):
            item = copy.deepcopy(base)
            item["dispositions"][1] = {
                "status": "Reviewed",
                "reason": f"verified transition fixture {index}",
            }
            snapshots.append(item)
        return tuple(build_review_package(item)[0] for item in snapshots)

    def delta(self, earlier_name, earlier, later_name, later):
        result = compare_review_packages(earlier_name, earlier, later_name, later)
        return build_review_delta_export(result)[0]

    def multipart(self, uploads):
        boundary = "----review-timeline-boundary"
        chunks: list[bytes] = []
        for filename, payload in uploads:
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(
                f'Content-Disposition: form-data; name="delta_export"; filename="{filename}"\r\n'.encode()
            )
            chunks.append(b"Content-Type: application/zip\r\n\r\n")
            chunks.append(payload)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        return body, {
            "Content-Type": f'multipart/form-data; boundary="{boundary}"',
            "Content-Length": str(len(body)),
        }

    def parser_handler(self, *, content_type, content_length, payload=b""):
        return SimpleNamespace(
            headers={
                "Content-Type": content_type,
                "Content-Length": content_length,
            },
            rfile=io.BytesIO(payload),
        )

    def test_home_and_get_page_are_available_without_session(self):
        status, _, home = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Review Timeline", home)
        self.assertIn(b"href='/review-timeline'", home)

        status, _, page = self.request("GET", "/review-timeline")
        self.assertEqual(status, 200)
        self.assertIn(b"Build Review Timeline", page)
        self.assertIn(b"multiple required", page)
        self.assertIn(b"Each Delta evidence ZIP is limited to 50 MB", page)
        self.assertEqual(SESSIONS, {})

    def test_timeline_multipart_has_dedicated_aggregate_limit_above_legacy_26_mb(self):
        self.assertEqual(MAX_DELTA_EXPORT_BYTES, 50 * 1024 * 1024)
        self.assertGreater(TIMELINE_MAX_REQUEST_BYTES, 26 * 1024 * 1024)
        self.assertGreaterEqual(TIMELINE_MAX_REQUEST_BYTES, 10 * MAX_DELTA_EXPORT_BYTES)

        boundary = "----timeline-parser-test"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="delta_export"; filename="a.zip"\r\n'
            "Content-Type: application/zip\r\n\r\n"
            "abc\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        handler = self.parser_handler(
            content_type=f'multipart/form-data; boundary="{boundary}"',
            content_length=str(len(body)),
            payload=body,
        )
        message = _timeline_multipart_message(handler)
        self.assertTrue(message.is_multipart())

    def test_timeline_multipart_rejects_malformed_aggregate_envelopes_before_evidence_use(self):
        boundary = "----timeline-malformed-test"
        content_type = f'multipart/form-data; boundary="{boundary}"'

        with self.assertRaisesRegex(InputError, "must use multipart form data"):
            _timeline_multipart_message(
                self.parser_handler(
                    content_type="application/octet-stream",
                    content_length="3",
                    payload=b"abc",
                )
            )

        with self.assertRaisesRegex(InputError, "invalid Content-Length"):
            _timeline_multipart_message(
                self.parser_handler(
                    content_type=content_type,
                    content_length="not-an-integer",
                )
            )

        with self.assertRaisesRegex(InputError, "exceeds the local"):
            _timeline_multipart_message(
                self.parser_handler(
                    content_type=content_type,
                    content_length=str(TIMELINE_MAX_REQUEST_BYTES + 1),
                )
            )

        declared = 100
        with self.assertRaisesRegex(InputError, "ended before its declared Content-Length"):
            _timeline_multipart_message(
                self.parser_handler(
                    content_type=content_type,
                    content_length=str(declared),
                    payload=b"short",
                )
            )

        malformed = b"this is not multipart form data"
        with self.assertRaisesRegex(InputError, "malformed multipart form data"):
            _timeline_multipart_message(
                self.parser_handler(
                    content_type=content_type,
                    content_length=str(len(malformed)),
                    payload=malformed,
                )
            )

        self.assertEqual(SESSIONS, {})

    def test_detail_cells_are_escaped_and_character_bounded(self):
        rendered = _cell("<tag>" + "x" * (MAX_TIMELINE_DETAIL_CELL_CHARS + 50))
        self.assertIn("&lt;tag&gt;", rendered)
        self.assertNotIn("<tag>", rendered)
        self.assertTrue(rendered.endswith("…"))
        self.assertLessEqual(len(rendered), MAX_TIMELINE_DETAIL_CELL_CHARS + 10)

    def test_reversed_upload_order_builds_sha_chain_with_escaped_labels_and_no_session(self):
        a, b, c, _d = self.packages()
        ab = self.delta("A.zip", a, "B-original.zip", b)
        bc = self.delta("B-renamed.zip", b, "C.zip", c)
        body, headers = self.multipart([
            ("<evil&bc>.zip", bc),
            ("ab.delta.zip", ab),
        ])
        status, _, page = self.request("POST", "/review-timeline", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Review Timeline evidence chain", page)
        self.assertIn(b"Snapshots:</strong> 3", page)
        self.assertIn(b"Transitions:</strong> 2", page)
        self.assertIn(b"exact package SHA-256 chain verified", page)
        self.assertIn(b"B-original.zip, B-renamed.zip", page)
        self.assertIn(b"ab.delta.zip", page)
        self.assertIn(b"&lt;evil&amp;bc&gt;.zip", page)
        self.assertNotIn(b"<evil&bc>.zip", page)
        ab_position = page.find(b"ab.delta.zip")
        bc_position = page.find(b"&lt;evil&amp;bc&gt;.zip")
        self.assertGreater(ab_position, -1)
        self.assertGreater(bc_position, ab_position)
        self.assertIn(b"Transition chronology only", page)
        self.assertIn(b"not a trend score", page)
        self.assertIn(b"Bounded transition evidence details", page)
        self.assertIn(b"REVIEW_CHANGED", page)
        self.assertIn(b"&lt;evil&amp;review&gt;", page)
        self.assertNotIn(b"<evil&review>", page)
        self.assertIn(b"UNCHANGED rows remain represented", page)
        self.assertIn(b"Showing all 1 verified changed finding rows", page)
        self.assertIn(b"do not imply improvement, regression", page)
        self.assertEqual(SESSIONS, {})

    def test_ten_transition_chain_succeeds_out_of_order_without_session(self):
        packages = self.long_chain_packages()
        uploads = []
        for index in range(10):
            payload = self.delta(
                f"snapshot-{index}.zip",
                packages[index],
                f"snapshot-{index + 1}.zip",
                packages[index + 1],
            )
            uploads.append((f"transition-{index:02d}.delta.zip", payload))

        body, headers = self.multipart(list(reversed(uploads)))
        status, _, page = self.request("POST", "/review-timeline", body, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Snapshots:</strong> 11", page)
        self.assertIn(b"Transitions:</strong> 10", page)
        self.assertIn(b"exact package SHA-256 chain verified", page)
        first = page.find(b"transition-00.delta.zip")
        last = page.find(b"transition-09.delta.zip")
        self.assertGreater(first, -1)
        self.assertGreater(last, first)
        self.assertEqual(SESSIONS, {})

    def test_disconnected_or_invalid_inputs_fail_safely_without_session(self):
        a, b, c, d = self.packages()
        ab = self.delta("A.zip", a, "B.zip", b)
        cd = self.delta("C.zip", c, "D.zip", d)
        body, headers = self.multipart([("ab.zip", ab), ("cd.zip", cd)])
        status, response_headers, page = self.request("POST", "/review-timeline", body, headers)
        self.assertEqual(status, 400)
        self.assertIn("text/html", response_headers["Content-Type"])
        self.assertIn(b"Timeline failed", page)
        self.assertRegex(page, re.compile(b"connected acyclic linear chain|disconnected"))
        self.assertEqual(SESSIONS, {})

        body, headers = self.multipart([("only.zip", ab)])
        status, _, page = self.request("POST", "/review-timeline", body, headers)
        self.assertEqual(status, 400)
        self.assertIn(b"Choose at least 2", page)
        self.assertEqual(SESSIONS, {})


if __name__ == "__main__":
    unittest.main()
