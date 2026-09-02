from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_delta import compare_review_packages
from review_delta_export import build_review_delta_export
from review_package import build_review_package
from review_timeline import build_review_timeline


class ReviewTimelineTests(unittest.TestCase):
    def base_session(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }

    def package_chain(self):
        a = self.base_session()
        b = copy.deepcopy(a)
        c = copy.deepcopy(a)
        d = copy.deepcopy(a)
        b["dispositions"][1] = {"status": "Reviewed", "reason": "A to B"}
        c["dispositions"][1] = {"status": "Reviewed", "reason": "A to B"}
        c["dispositions"][2] = {"status": "Needs correction", "reason": "B to C"}
        d["dispositions"][1] = {"status": "Accepted", "reason": "A to D"}
        return tuple(build_review_package(session)[0] for session in (a, b, c, d))

    def delta(self, earlier_name, earlier, later_name, later):
        result = compare_review_packages(earlier_name, earlier, later_name, later)
        return build_review_delta_export(result)[0]

    def valid_chain(self):
        a, b, c, _ = self.package_chain()
        ab = self.delta("A.zip", a, "B-first-name.zip", b)
        bc = self.delta("B-renamed.zip", b, "C.zip", c)
        return a, b, c, ab, bc

    def test_valid_chain_is_ordered_by_package_sha_not_upload_order(self):
        a, b, c, ab, bc = self.valid_chain()
        forward = build_review_timeline([("ab.delta.zip", ab), ("bc.delta.zip", bc)])
        reversed_input = build_review_timeline([("bc.delta.zip", bc), ("ab.delta.zip", ab)])
        self.assertEqual(forward, reversed_input)
        self.assertEqual(forward["timeline_format"], "civil-estimate-review-timeline")
        self.assertEqual(forward["timeline_version"], 1)
        self.assertEqual(forward["delta_bundle_count"], 2)
        self.assertEqual(forward["snapshot_count"], 3)
        self.assertEqual(
            [item["package_sha256"] for item in forward["snapshots"]],
            [hashlib.sha256(payload).hexdigest() for payload in (a, b, c)],
        )
        self.assertEqual(
            [item["delta_filename"] for item in forward["transitions"]],
            ["ab.delta.zip", "bc.delta.zip"],
        )
        middle = forward["snapshots"][1]
        self.assertEqual(middle["package_filename_aliases"], ["B-first-name.zip", "B-renamed.zip"])
        self.assertTrue(forward["continuity_verified_by_package_sha256"])
        self.assertFalse(forward["session_created"])
        self.assertFalse(forward["re_audit_performed"])
        self.assertFalse(forward["source_currency_inferred"])
        self.assertFalse(forward["quality_trend_inferred"])
        self.assertFalse(forward["improvement_regression_inferred"])
        self.assertFalse(forward["readiness_inferred"])
        self.assertFalse(forward["heavybid_import_validated"])

    def test_duplicate_bundle_and_duplicate_transition_fail_closed(self):
        _a, _b, _c, ab, _bc = self.valid_chain()
        with self.assertRaisesRegex(ValueError, "same Delta evidence bundle"):
            build_review_timeline([("one.zip", ab), ("two.zip", ab)])

        a, b, _c, _d = self.package_chain()
        ab2 = self.delta("A-second.zip", a, "B-second.zip", b)
        self.assertNotEqual(hashlib.sha256(ab).hexdigest(), hashlib.sha256(ab2).hexdigest())
        with self.assertRaisesRegex(ValueError, "duplicate review-package transition"):
            build_review_timeline([("one.zip", ab), ("two.zip", ab2)])

    def test_branch_merge_cycle_and_disconnected_graphs_fail_closed(self):
        a, b, c, d = self.package_chain()
        ab = self.delta("A.zip", a, "B.zip", b)
        ac = self.delta("A.zip", a, "C.zip", c)
        bc = self.delta("B.zip", b, "C.zip", c)
        dc = self.delta("D.zip", d, "C.zip", c)
        ba = self.delta("B.zip", b, "A.zip", a)
        cd = self.delta("C.zip", c, "D.zip", d)

        with self.assertRaisesRegex(ValueError, "branching"):
            build_review_timeline([("ab.zip", ab), ("ac.zip", ac)])
        with self.assertRaisesRegex(ValueError, "merging"):
            build_review_timeline([("bc.zip", bc), ("dc.zip", dc)])
        with self.assertRaisesRegex(ValueError, "connected acyclic linear chain|cycle"):
            build_review_timeline([("ab.zip", ab), ("ba.zip", ba)])
        with self.assertRaisesRegex(ValueError, "connected acyclic linear chain|disconnected"):
            build_review_timeline([("ab.zip", ab), ("cd.zip", cd)])

    def test_invalid_sha_and_conflicting_same_snapshot_metadata_fail_closed(self):
        a, b, c, _d = self.package_chain()
        ab_result = compare_review_packages("A.zip", a, "B.zip", b)
        ab_result["earlier"]["package_sha256"] = "not-a-sha"
        invalid_sha = build_review_delta_export(ab_result)[0]
        bc = self.delta("B.zip", b, "C.zip", c)
        with self.assertRaisesRegex(ValueError, "valid review-package SHA-256"):
            build_review_timeline([("invalid.zip", invalid_sha), ("bc.zip", bc)])

        ab = self.delta("A.zip", a, "B.zip", b)
        bc_result = compare_review_packages("B-renamed.zip", b, "C.zip", c)
        bc_result["earlier"]["source_filename"] = "conflicting-source.csv"
        conflicting = build_review_delta_export(bc_result)[0]
        with self.assertRaisesRegex(ValueError, "conflicting snapshot lineage"):
            build_review_timeline([("ab.zip", ab), ("conflict.zip", conflicting)])

    def test_self_transition_and_unsupported_lineage_versions_fail_closed(self):
        a, b, c, _d = self.package_chain()
        aa = self.delta("A-first.zip", a, "A-second.zip", a)
        bc = self.delta("B.zip", b, "C.zip", c)
        with self.assertRaisesRegex(ValueError, "self-transition"):
            build_review_timeline([("aa.zip", aa), ("bc.zip", bc)])

        ab_result = compare_review_packages("A.zip", a, "B.zip", b)
        ab_result["earlier"]["package_version"] = 2
        unsupported_package = build_review_delta_export(ab_result)[0]
        with self.assertRaisesRegex(ValueError, "review-package version 1"):
            build_review_timeline([("unsupported-package.zip", unsupported_package), ("bc.zip", bc)])

        ab_result = compare_review_packages("A.zip", a, "B.zip", b)
        ab_result["earlier"]["integrity_version"] = 2
        unsupported_integrity = build_review_delta_export(ab_result)[0]
        with self.assertRaisesRegex(ValueError, "integrity version 1"):
            build_review_timeline([("unsupported-integrity.zip", unsupported_integrity), ("bc.zip", bc)])

    def test_minimum_and_maximum_bundle_counts_are_bounded(self):
        _a, _b, _c, ab, _bc = self.valid_chain()
        with self.assertRaisesRegex(ValueError, "at least 2"):
            build_review_timeline([("only.zip", ab)])
        with self.assertRaisesRegex(ValueError, "at most 10"):
            build_review_timeline([(f"d{i}.zip", ab) for i in range(11)])


if __name__ == "__main__":
    unittest.main()
