from __future__ import annotations

import http.client
import importlib
import re
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import onboarding
import package_verification
import reference_session
import server_legacy as legacy
from runtime_composition import compose_public_runtime, public_feature_names
from runtime_context import PAGE_KIND_REVIEW_FINDINGS, page_context
from server import Handler, SESSIONS, ThreadingHTTPServer


_REVIEW_BODY = """
<section class='card' id='findings'>
<form action='/review' method='post'><input type='hidden' name='token' value='token'>
<table aria-describedby='findings-caption'><caption id='findings-caption'>Findings</caption>
<thead><tr><th>Reason / note</th></tr></thead><tbody></tbody></table>
<p><button type='submit'>Save visible review states</button></p></form>
</section>
"""


class RuntimeCompositionUnitTests(unittest.TestCase):
    def test_feature_order_is_explicit_and_stable(self):
        self.assertEqual(
            public_feature_names(),
            (
                "accessibility_semantics",
                "bulk_review_ui",
                "review_view_context",
                "operational_reference_ui",
                "archived_review_ui",
                "review_delta_ui",
                "review_delta_verification_ui",
                "review_timeline_ui",
            ),
        )

    def test_composition_is_idempotent(self):
        before = (
            legacy.page,
            legacy._review_row,
            legacy.Handler.do_GET,
            legacy.Handler.do_POST,
            legacy.home,
            reference_session.reference_panel,
            reference_session.validate_reference_submission,
            reference_session._operational_panel,
            package_verification.verification_page_body,
        )
        self.assertEqual(compose_public_runtime(), public_feature_names())
        self.assertEqual(compose_public_runtime(), public_feature_names())
        after = (
            legacy.page,
            legacy._review_row,
            legacy.Handler.do_GET,
            legacy.Handler.do_POST,
            legacy.home,
            reference_session.reference_panel,
            reference_session.validate_reference_submission,
            reference_session._operational_panel,
            package_verification.verification_page_body,
        )
        self.assertEqual(before, after)

    def test_onboarding_reload_has_no_runtime_install_side_effects(self):
        before = (
            legacy.page,
            legacy._review_row,
            legacy.Handler.do_GET,
            legacy.Handler.do_POST,
            legacy.home,
        )
        importlib.reload(onboarding)
        after = (
            legacy.page,
            legacy._review_row,
            legacy.Handler.do_GET,
            legacy.Handler.do_POST,
            legacy.home,
        )
        self.assertEqual(before, after)
        self.assertIn("Fictional training data only", onboarding.guide_body())

    def test_explicit_page_kind_not_display_title_controls_review_augmentation(self):
        plain = legacy.page("Audit results", _REVIEW_BODY).decode("utf-8")
        self.assertNotIn("Select for bulk", plain)
        self.assertNotIn("review-view-query", plain)

        with page_context(PAGE_KIND_REVIEW_FINDINGS):
            rendered = legacy.page("Renamed estimator review workspace", _REVIEW_BODY).decode("utf-8")
        self.assertIn("Select for bulk", rendered)
        self.assertIn("Bulk review explicitly selected findings", rendered)
        self.assertIn("review-view-query", rendered)
        self.assertIn("lang='en'", rendered)
        self.assertIn("id='main-content'", rendered)


class RuntimeCompositionHttpTests(unittest.TestCase):
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

    def test_fully_composed_public_server_preserves_feature_surface(self):
        status, _, home = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(home.count(b"/guide"), 1)
        self.assertEqual(home.count(b"/verify-package"), 1)
        self.assertEqual(home.count(b"/compare-review-packages"), 1)
        self.assertEqual(home.count(b"/verify-review-delta"), 1)
        self.assertEqual(home.count(b"/review-timeline"), 1)
        self.assertIn(b"lang='en'", home)
        self.assertIn(b"id='main-content'", home)

        for path, marker in (
            ("/guide", b"Fictional training data only"),
            ("/verify-package", b"Review package verification"),
            ("/continue-review-package", b"Review-package re-open contract"),
            ("/compare-review-packages", b"Compare two review snapshots"),
            ("/verify-review-delta", b"Verify Review Delta evidence bundle"),
            ("/review-timeline", b"Build Review Timeline"),
        ):
            status, _, page = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(marker, page)

        status, _, mapping = self.request("POST", "/sample", b"", {"Content-Length": "0"})
        self.assertEqual(status, 200)
        token_match = re.search(rb"name='token' value='([^']+)'", mapping)
        self.assertIsNotNone(token_match)
        token = token_match.group(1).decode()
        form = [("token", token)]
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
            form.append((f"map__synthetic_civil_estimate__{field}", header))
        status, _, results = self.post_form("/audit", form)
        self.assertEqual(status, 200)
        self.assertIn(b"Select for bulk", results)
        self.assertIn(b"Bulk review explicitly selected findings", results)
        self.assertIn(b"name='view_query'", results)
        self.assertIn(b"Review attention summary", results)
        self.assertIn(b"Governed reference validation", results)
        self.assertIn(b"Operational Activity evidence", results)
        self.assertIn(b"Not available for this audit", results)
        self.assertIn(b"global-skip", results)

        status, _, stable = self.request("GET", f"/results?token={token}&severity=Priority&sort_by=source")
        self.assertEqual(status, 200)
        self.assertIn(b"Select for bulk", stable)
        self.assertIn(b"name='view_query'", stable)
        self.assertIn(b"<option value='Priority' selected>Priority</option>", stable)
        self.assertIn(b"<option value='source' selected>Source sheet / row</option>", stable)


if __name__ == "__main__":
    unittest.main()
