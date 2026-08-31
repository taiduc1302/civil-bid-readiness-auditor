from __future__ import annotations

import copy
import http.client
import re
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from server import Handler, SESSIONS, ThreadingHTTPServer


class BulkReviewUiTests(unittest.TestCase):
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

    def preview(self, token: str, ids, status="Reviewed", reason="Bulk human review", ownership=True):
        pairs = [("token", token)]
        pairs.extend(("bulk_id", str(finding_id)) for finding_id in ids)
        pairs.extend([("bulk_status", status), ("bulk_reason", reason)])
        if ownership:
            pairs.append(("bulk_ownership", "yes"))
        status_code, _, body = self.post_form("/bulk-review/preview", pairs)
        plan_token_match = re.search(rb"name='plan_token' value='([^']+)'", body)
        plan_token = plan_token_match.group(1).decode() if plan_token_match else ""
        return status_code, body, plan_token

    def apply(self, token: str, plan_token: str, confirm=True):
        pairs = [("token", token), ("plan_token", plan_token)]
        if confirm:
            pairs.append(("confirm_bulk_apply", "yes"))
        return self.post_form("/bulk-review/apply", pairs)

    def test_results_page_has_explicit_checkboxes_and_no_select_all(self):
        token, body = self.audited_sample()
        self.assertIn(b"Select for bulk", body)
        self.assertIn(b"name='bulk_id' value='1'", body)
        self.assertIn(b"Bulk review explicitly selected findings", body)
        self.assertIn(b"Preview bulk action", body)
        self.assertIn(b"Current filters, grouping, or hidden rows never select findings automatically", body)
        self.assertNotIn(b"Select all", body)
        self.assertIn(token.encode(), body)

    def test_preview_records_one_time_plan_but_does_not_mutate_dispositions(self):
        token, _ = self.audited_sample()
        before = copy.deepcopy(SESSIONS[token]["dispositions"])
        status, body, plan_token = self.preview(token, [1, 2])
        self.assertEqual(status, 200)
        self.assertTrue(plan_token)
        self.assertIn(b"No review state has changed", body)
        self.assertIn(b"Selected findings:</strong> 2", body)
        self.assertIn(b"Exact findings selected", body)
        self.assertEqual(SESSIONS[token]["dispositions"], before)
        self.assertEqual(list(SESSIONS[token]["bulk_review_plans"]), [plan_token])

    def test_confirmed_apply_is_atomic_and_replay_fails(self):
        token, _ = self.audited_sample()
        status, _, plan_token = self.preview(token, [1, 2], status="Reviewed", reason="Checked together")
        self.assertEqual(status, 200)

        status, _, body = self.apply(token, plan_token)
        self.assertEqual(status, 200)
        self.assertIn(b"Bulk review applied to 2 explicitly selected finding", body)
        self.assertEqual(SESSIONS[token]["dispositions"][1], {"status": "Reviewed", "reason": "Checked together"})
        self.assertEqual(SESSIONS[token]["dispositions"][2], {"status": "Reviewed", "reason": "Checked together"})
        self.assertEqual(SESSIONS[token]["dispositions"][3]["status"], "Open")
        self.assertNotIn(plan_token, SESSIONS[token].get("bulk_review_plans", {}))

        status, _, replay = self.apply(token, plan_token)
        self.assertEqual(status, 400)
        self.assertIn(b"missing, expired, replaced, or already used", replay)
        self.assertEqual(SESSIONS[token]["dispositions"][1]["status"], "Reviewed")

    def test_concurrent_apply_replay_allows_exactly_one_success(self):
        token, _ = self.audited_sample()
        status, _, plan_token = self.preview(token, [1, 2], status="Accepted", reason="One-time concurrent test")
        self.assertEqual(status, 200)
        start = threading.Barrier(3)
        result_lock = threading.Lock()
        outcomes = []

        def worker():
            start.wait()
            outcome = self.apply(token, plan_token)
            with result_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join(5.0)
            self.assertFalse(thread.is_alive())

        self.assertEqual(sorted(item[0] for item in outcomes), [200, 400])
        bodies = [item[2] for item in outcomes]
        self.assertEqual(sum(b"Bulk review applied to 2 explicitly selected finding" in body for body in bodies), 1)
        self.assertEqual(sum(b"missing, expired, replaced, or already used" in body for body in bodies), 1)
        self.assertEqual(SESSIONS[token]["dispositions"][1], {"status": "Accepted", "reason": "One-time concurrent test"})
        self.assertEqual(SESSIONS[token]["dispositions"][2], {"status": "Accepted", "reason": "One-time concurrent test"})
        self.assertNotIn(plan_token, SESSIONS[token].get("bulk_review_plans", {}))

    def test_missing_selection_ownership_and_suppression_reason_fail_without_mutation(self):
        token, _ = self.audited_sample()
        before = copy.deepcopy(SESSIONS[token]["dispositions"])

        status, body, _ = self.preview(token, [], ownership=True)
        self.assertEqual(status, 400)
        self.assertIn(b"at least one explicitly selected", body)
        self.assertIn(f"/results?token={token}#findings".encode(), body)
        self.assertEqual(SESSIONS[token]["dispositions"], before)

        status, body, _ = self.preview(token, [1], ownership=False)
        self.assertEqual(status, 400)
        self.assertIn(b"human-ownership", body)
        self.assertIn(f"/results?token={token}#findings".encode(), body)
        self.assertEqual(SESSIONS[token]["dispositions"], before)

        status, body, _ = self.preview(token, [1], status="Suppressed", reason="", ownership=True)
        self.assertEqual(status, 400)
        self.assertIn(b"Suppressed findings require a review reason", body)
        self.assertIn(f"/results?token={token}#findings".encode(), body)
        self.assertEqual(SESSIONS[token]["dispositions"], before)

    def test_missing_apply_confirmation_does_not_mutate_or_consume_plan(self):
        token, _ = self.audited_sample()
        _, _, plan_token = self.preview(token, [1])
        before = copy.deepcopy(SESSIONS[token]["dispositions"])
        status, _, body = self.apply(token, plan_token, confirm=False)
        self.assertEqual(status, 400)
        self.assertIn(b"requires explicit confirmation", body)
        self.assertIn(f"/results?token={token}#findings".encode(), body)
        self.assertEqual(SESSIONS[token]["dispositions"], before)
        self.assertIn(plan_token, SESSIONS[token]["bulk_review_plans"])

    def test_stale_multi_target_plan_fails_without_partial_target_update(self):
        token, _ = self.audited_sample()
        _, _, plan_token = self.preview(token, [1, 2], status="Accepted", reason="Previewed together")

        form = [("token", token), ("status__2", "Needs correction"), ("reason__2", "Changed after preview")]
        status, _, _ = self.post_form("/review", form)
        self.assertEqual(status, 200)
        self.assertEqual(SESSIONS[token]["dispositions"][1]["status"], "Open")
        self.assertEqual(SESSIONS[token]["dispositions"][2]["status"], "Needs correction")

        status, _, body = self.apply(token, plan_token)
        self.assertEqual(status, 400)
        self.assertIn(b"current review state changed", body)
        self.assertEqual(SESSIONS[token]["dispositions"][1]["status"], "Open")
        self.assertEqual(SESSIONS[token]["dispositions"][2], {"status": "Needs correction", "reason": "Changed after preview"})
        self.assertNotIn(plan_token, SESSIONS[token].get("bulk_review_plans", {}))

    def test_filtered_view_never_becomes_implicit_bulk_scope(self):
        token, _ = self.audited_sample()
        status, _, filtered = self.request("GET", f"/results?token={token}&severity=Priority")
        self.assertEqual(status, 200)
        self.assertIn(b"Select for bulk", filtered)

        before = copy.deepcopy(SESSIONS[token]["dispositions"])
        status, body, _ = self.preview(token, [], ownership=True)
        self.assertEqual(status, 400)
        self.assertIn(b"at least one explicitly selected", body)
        self.assertEqual(SESSIONS[token]["dispositions"], before)

    def test_new_preview_invalidates_older_preview(self):
        token, _ = self.audited_sample()
        _, _, first = self.preview(token, [1])
        _, _, second = self.preview(token, [2])
        self.assertNotEqual(first, second)
        self.assertNotIn(first, SESSIONS[token]["bulk_review_plans"])
        self.assertIn(second, SESSIONS[token]["bulk_review_plans"])

        status, _, body = self.apply(token, first)
        self.assertEqual(status, 400)
        self.assertIn(b"missing, expired, replaced, or already used", body)


if __name__ == "__main__":
    unittest.main()
