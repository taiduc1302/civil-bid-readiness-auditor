from __future__ import annotations

import io
import json
import unittest
import zipfile

from review_delta_export import build_review_delta_export, verify_review_delta_export
from review_timeline_export import (
    build_review_timeline_export,
    verify_review_timeline_export,
)


FINDING_TYPES = (
    "UNCHANGED",
    "REVIEW_CHANGED",
    "EVIDENCE_CHANGED",
    "EVIDENCE_AND_REVIEW_CHANGED",
    "ADDED",
    "REMOVED",
)
REFERENCE_TYPES = ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")


def counts(kind: str) -> dict[str, int]:
    return {key: int(key == kind) for key in FINDING_TYPES}


def zero_reference_counts() -> dict[str, int]:
    return {key: 0 for key in REFERENCE_TYPES}


def lineage(label: str) -> dict[str, object]:
    digit = {"a": "1", "b": "2", "c": "3"}[label]
    return {
        "package_filename": f"snapshot-{label}.zip",
        "package_sha256": digit * 64,
        "package_format": "civil-estimate-review-package",
        "package_version": 1,
        "integrity_version": 1,
        "source_session_mode": "archived_review_snapshot",
        "source_filename": "estimate.csv",
        "rows_reviewed": 1,
    }


def finding(change_type: str, before_status: str, after_status: str) -> dict[str, object]:
    return {
        "change_type": change_type,
        "anchor": {"sheet": "Sheet 1", "row": 7, "rule_id": "R001", "field": "quantity"},
        "evidence_fields_changed": [],
        "review_fields_changed": [] if change_type == "UNCHANGED" else ["status"],
        "before": {
            "severity": "High",
            "message": "Review source evidence",
            "evidence": "source value present",
            "recommended_action": "Human review",
        },
        "after": {
            "severity": "High",
            "message": "Review source evidence",
            "evidence": "source value present",
            "recommended_action": "Human review",
        },
        "before_review": {"status": before_status, "reason": ""},
        "after_review": {"status": after_status, "reason": ""},
    }


def comparison(earlier: str, later: str, change_type: str) -> dict[str, object]:
    before = "Open"
    after = "Open" if change_type == "UNCHANGED" else "Reviewed"
    return {
        "comparison_format": "civil-estimate-review-delta",
        "comparison_version": 1,
        "earlier": lineage(earlier),
        "later": lineage(later),
        "same_source_filename": True,
        "same_package_sha256": False,
        "finding_counts": counts(change_type),
        "finding_changes": [finding(change_type, before, after)],
        "reference_counts": zero_reference_counts(),
        "reference_changes": [],
        "reference_metadata_counts": zero_reference_counts(),
        "reference_metadata_changes": [],
        "session_created": False,
        "re_audit_performed": False,
        "correctness_inferred": False,
        "readiness_inferred": False,
        "heavybid_import_validated": False,
    }


def delta_pair() -> tuple[bytes, bytes]:
    first, _ = build_review_delta_export(comparison("a", "b", "UNCHANGED"))
    second, _ = build_review_delta_export(comparison("b", "c", "REVIEW_CHANGED"))
    return first, second


class ReviewTimelineExportTests(unittest.TestCase):
    def test_delta_canonical_full_evidence_is_opt_in_after_verification(self):
        first, _ = delta_pair()
        bounded = verify_review_delta_export(first)
        self.assertNotIn("canonical_comparison", bounded)
        full = verify_review_delta_export(first, include_canonical=True)
        self.assertEqual(full["canonical_comparison"]["finding_changes"][0]["change_type"], "UNCHANGED")
        self.assertFalse(full["heavybid_import_validated"])

    def test_export_is_byte_deterministic_for_same_evidence_regardless_upload_order(self):
        first, second = delta_pair()
        ordered, filename = build_review_timeline_export([
            ("transition-01.zip", first),
            ("transition-02.zip", second),
        ])
        reversed_input, _ = build_review_timeline_export([
            ("transition-02.zip", second),
            ("transition-01.zip", first),
        ])
        self.assertEqual(ordered, reversed_input)
        self.assertEqual(filename, "review_timeline_evidence_v1.zip")

        verified = verify_review_timeline_export(ordered)
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["snapshot_count"], 3)
        self.assertEqual(verified["transition_count"], 2)
        self.assertFalse(verified["heavybid_import_validated"])
        self.assertFalse(verified["session_created"])
        self.assertFalse(verified["persistence_created"])

    def test_export_has_exact_root_members_fixed_zip_time_and_full_unchanged_evidence(self):
        first, second = delta_pair()
        payload, _ = build_review_timeline_export([
            ("transition-02.zip", second),
            ("transition-01.zip", first),
        ])
        with zipfile.ZipFile(io.BytesIO(payload), "r") as book:
            names = [item.filename for item in book.infolist()]
            self.assertEqual(names, sorted(names))
            self.assertEqual(set(names), {
                "README.txt", "finding_changes.csv", "integrity.json", "manifest.json",
                "reference_changes.csv", "reference_metadata_changes.csv", "review_timeline.json",
                "snapshots.csv", "transitions.csv",
            })
            self.assertTrue(all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in book.infolist()))
            canonical = json.loads(book.read("review_timeline.json"))
            rows = [
                row
                for transition in canonical["transitions"]
                for row in transition["finding_changes"]
            ]
            self.assertEqual([row["change_type"] for row in rows], ["UNCHANGED", "REVIEW_CHANGED"])
            self.assertNotIn("generated_narrative", canonical)
            self.assertFalse(canonical["safety"]["heavybid_import_validated"])

    def test_tampering_is_rejected(self):
        first, second = delta_pair()
        payload, _ = build_review_timeline_export([
            ("transition-01.zip", first),
            ("transition-02.zip", second),
        ])
        source = zipfile.ZipFile(io.BytesIO(payload), "r")
        output = io.BytesIO()
        with source, zipfile.ZipFile(output, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == "review_timeline.json":
                    data += b" "
                target.writestr(info, data)
        with self.assertRaisesRegex(ValueError, "integrity check failed"):
            verify_review_timeline_export(output.getvalue())


if __name__ == "__main__":
    unittest.main()
