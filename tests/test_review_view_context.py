from __future__ import annotations

import http.client
import re
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from review_view_context import results_return_url, sanitize_view_query, view_filters
from server import Handler, SESSIONS, ThreadingHTTPServer


class ReviewViewContextUnitTests(unittest.TestCase):
    def test_only_known_view_keys_survive_and_return_url_is_local(self):
        raw = (
            "severity=Priority&sort_by=source&group_by=rule&ref_status=All&ref_sort=code"
            "&token=attacker&next=https%3A%2F%2Fevil.example%2Fx&severity=Low"
        )
        sanitized = sanitize_view_query(raw)
        self.assertIn("severity=Priority", sanitized)
        self.assertIn("sort_by=source", sanitized)
        self.assertIn("group_by=rule", sanitized)
        self.assertIn("ref_status=All", sanitized)
        self.assertIn("ref_sort=code", sanitized)
        self.assertNotIn("attacker", sanitized)
        self.assertNotIn("next", sanitized)
        self.assertNotIn("evil", sanitized)
        self.assertNotIn("severity=Low", sanitized)

        url = results_return_url("session-token", raw)
        self.assertTrue(url.startswith("/results?token=session-token&"))
        self.assertTrue(url.endswith("#findings"))
        self.assertNotIn("evil.example", url)
        self.assertNotIn("attacker", url)

        filters = view_filters(raw)
        self.assertEqual(filters["severity"], "Priority")
        self.assertEqual(filters["sort_by"], "source")
        self.assertEqual(filters["group_by"], "rule")
        self.assertEqual(filters["ref_status"], "All")


class ReviewViewContextServerTests(unittest.TestCase):
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
        encoded = urlencode(pairs, doseq=True).encode()
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
        status, _, body = self.post_form("/audit", mappings)
        self.assertEqual(status, 200)
        return token, body

    def view_query(self):
        return urlencode(
            [
                ("severity", "Priority"),
                ("q", "rate"),
                ("sort_by", "source"),
                ("group_by", "rule"),
                ("ref_status", "All"),
                ("ref_sort", "code"),
                ("ref_group", "type"),
            ]
        )

    def assert_view_preserved(self, body: bytes):
        self.assertIn(b"value='Priority' selected", body)
        self.assertIn(b"name='q' value='rate'", body)
        self.assertIn(b"value='source' selected", body)
        self.assertIn(b"value='rule' selected", body)
        self.assertIn(b"name='ref_status' value='All'", body)
        self.assertIn(b"name='ref_sort' value='code'", body)
        self.assertIn(b"name='ref_group' value='type'", body)

    def test_results_form_captures_current_local_query_for_post_actions(self):
        token, _ = self.audited_sample()
        query = self.view_query()
        status, _, body = self.request("GET", f"/results?token={token}&{query}")
        self.assertEqual(status, 200)
        self.assertIn(b"name='view_query' id='review-view-query'", body)
        self.assertIn(b"window.location.search", body)
        self.assert_view_preserved(body)

    def test_save_visible_review_states_preserves_view(self):
        token, _ = self.audited_sample()
        query = self.view_query()
        status, _, body = self.post_form(
            "/review",
            [
                ("token", token),
                ("status__1", "Reviewed"),
                ("reason__1", "Checked in filtered view"),
                ("view_query", query),
            ],
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Review states saved", body)
        self.assertEqual(SESSIONS[token]["dispositions"][1]["status"], "Reviewed")
        self.assert_view_preserved(body)

    def test_bulk_preview_cancel_and_apply_preserve_view(self):
        token, _ = self.audited_sample()
        query = self.view_query()
        status, _, preview = self.post_form(
            "/bulk-review/preview",
            [
                ("token", token),
                ("bulk_id", "1"),
                ("bulk_status", "Reviewed"),
                ("bulk_reason", "Bulk filtered review"),
                ("bulk_ownership", "yes"),
                ("view_query", query),
            ],
        )
        self.assertEqual(status, 200)
        plan_token = re.search(rb"name='plan_token' value='([^']+)'", preview).group(1).decode()
        self.assertIn(b"Cancel and return to findings", preview)
        self.assertIn(b"severity%3DPriority", preview)
        self.assertIn(b"ref_group%3Dtype", preview)

        status, _, body = self.post_form(
            "/bulk-review/apply",
            [
                ("token", token),
                ("plan_token", plan_token),
                ("view_query", query),
                ("confirm_bulk_apply", "yes"),
            ],
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Bulk review applied", body)
        self.assertEqual(SESSIONS[token]["dispositions"][1]["status"], "Reviewed")
        self.assert_view_preserved(body)

    def test_bulk_error_return_drops_redirect_like_unknown_parameters(self):
        token, _ = self.audited_sample()
        raw = "severity=Priority&next=https%3A%2F%2Fevil.example%2Fx&token=attacker"
        status, _, body = self.post_form(
            "/bulk-review/preview",
            [
                ("token", token),
                ("bulk_status", "Reviewed"),
                ("bulk_ownership", "yes"),
                ("view_query", raw),
            ],
        )
        self.assertEqual(status, 400)
        self.assertIn(f"/results?token={token}".encode(), body)
        self.assertIn(b"severity=Priority", body)
        self.assertNotIn(b"evil.example", body)
        self.assertNotIn(b"attacker", body)
        self.assertNotIn(b"next=", body)


if __name__ == "__main__":
    unittest.main()
