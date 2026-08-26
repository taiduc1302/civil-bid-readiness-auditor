from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from reference_views import filter_reference_results, group_reference_results, sort_reference_results


class ReferenceViewTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            {"sheet": "Estimate", "source_row": 5, "reference_type": "resource", "status": "MATCH", "code": "M-1", "reference_code": "M-1", "reference_unit": "EA", "message": "Exact governed reference match."},
            {"sheet": "Estimate", "source_row": 3, "reference_type": "activity", "status": "NO_MATCH", "code": "A-X", "reference_code": "", "reference_unit": "", "message": "Code is not present."},
            {"sheet": "Alternate", "source_row": 9, "reference_type": "resource", "status": "UNIT_MISMATCH", "code": "M-2", "reference_code": "M-2", "reference_unit": "M", "message": "Source unit differs."},
            {"sheet": "Estimate", "source_row": 7, "reference_type": "activity", "status": "NOT_CHECKED", "code": "", "reference_code": "", "reference_unit": "", "message": "No source code supplied."},
        ]
        self.metadata = [
            {"role": "activity", "filename": "activities.csv", "revision": "Rev A", "sha256": "abc"},
            {"role": "resource", "filename": "resources.csv", "revision": "Rev B", "sha256": "def"},
        ]

    def test_default_view_is_exceptions_only(self):
        filtered = filter_reference_results(self.results, self.metadata)
        self.assertEqual([item["status"] for item in filtered], ["NO_MATCH", "UNIT_MISMATCH", "NOT_CHECKED"])

    def test_status_type_and_text_filters_compose(self):
        filtered = filter_reference_results(
            self.results, self.metadata, status="All", reference_type="resource", text="Rev B"
        )
        self.assertEqual([item["code"] for item in filtered], ["M-1", "M-2"])
        self.assertEqual([item["status"] for item in filter_reference_results(self.results, self.metadata, status="NO_MATCH")], ["NO_MATCH"])

    def test_text_search_includes_reference_filename_and_revision(self):
        filtered = filter_reference_results(self.results, self.metadata, status="All", text="activities.csv")
        self.assertEqual([item["reference_type"] for item in filtered], ["activity", "activity"])

    def test_invalid_filters_fail_safe(self):
        filtered = filter_reference_results(self.results, self.metadata, status="bad", reference_type="bad")
        self.assertEqual([item["status"] for item in filtered], ["NO_MATCH", "UNIT_MISMATCH", "NOT_CHECKED"])

    def test_sorting_is_deterministic_and_non_mutating(self):
        before = [dict(item) for item in self.results]
        self.assertEqual([item["status"] for item in sort_reference_results(self.results, "status")], ["NO_MATCH", "UNIT_MISMATCH", "NOT_CHECKED", "MATCH"])
        self.assertEqual([item["source_row"] for item in sort_reference_results(self.results, "source")], [9, 3, 5, 7])
        self.assertEqual([item["code"] for item in sort_reference_results(self.results, "code")], ["", "A-X", "M-1", "M-2"])
        self.assertEqual(self.results, before)

    def test_unknown_sort_fails_safe_to_status(self):
        expected = sort_reference_results(self.results, "status")
        actual = sort_reference_results(self.results, "unknown")
        self.assertEqual(actual, expected)

    def test_grouping_preserves_current_order(self):
        ordered = sort_reference_results(self.results, "status")
        groups = group_reference_results(ordered, "status")
        self.assertEqual([label for label, _ in groups], ["NO_MATCH", "UNIT_MISMATCH", "NOT_CHECKED", "MATCH"])
        self.assertEqual(group_reference_results(ordered, "bad"), [("", ordered)])


if __name__ == "__main__":
    unittest.main()
