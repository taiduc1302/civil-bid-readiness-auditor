from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from archived_review import ARCHIVED_REVIEW_SESSION_MODE, build_archived_review_session
from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_package import build_review_package


class ArchivedReviewContractTests(unittest.TestCase):
    def review_package(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        session = {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }
        return build_review_package(session)

    def test_verified_package_builds_review_only_session_without_source_rows(self):
        package, package_name = self.review_package()
        session = build_archived_review_session(package_name, package)

        self.assertEqual(session["session_mode"], ARCHIVED_REVIEW_SESSION_MODE)
        self.assertEqual(session["sheets"], {})
        self.assertNotIn("audit_sheets", session)
        self.assertEqual(len(session["result"]["findings"]), 14)
        self.assertEqual(session["result"]["review_metrics"]["status"], "Archived review snapshot — no estimate re-audit performed")
        self.assertIn("original estimate bytes are absent", session["result"]["score_explanation"])
        self.assertEqual(session["dispositions"][1]["status"], "Open")
        self.assertFalse(session["archived_snapshot_origin"]["re_audit_performed"])
        self.assertFalse(session["archived_snapshot_origin"]["original_estimate_bytes_available"])
        self.assertFalse(session["archived_snapshot_origin"]["original_reference_bytes_available"])
        self.assertFalse(session["archived_snapshot_origin"]["reference_rerun_available"])
        self.assertEqual(len(session["archived_snapshot_origin"]["package_sha256"]), 64)

    def test_archived_continuation_rejects_unsupported_source_session_context(self):
        package, package_name = self.review_package()
        # An ordinary v1 package has no session_context and remains eligible.
        session = build_archived_review_session(package_name, package)
        self.assertEqual(session["archived_snapshot_origin"]["source_session_mode"], "legacy_package_v1_unspecified")


if __name__ == "__main__":
    unittest.main()
