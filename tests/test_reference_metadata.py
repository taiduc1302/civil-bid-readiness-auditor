from __future__ import annotations

import csv
import hashlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from reference_metadata import build_reference_metadata, metadata_by_role, reference_review_csv


class ReferenceMetadataTests(unittest.TestCase):
    def test_metadata_hash_size_and_blank_revision_are_explicit(self):
        payload = b"resource_code,unit\nM-1,EA\n"
        meta = build_reference_metadata("resource", "resource.csv", payload, "")
        self.assertEqual(meta["role"], "resource")
        self.assertEqual(meta["filename"], "resource.csv")
        self.assertEqual(meta["revision"], "")
        self.assertEqual(meta["size_bytes"], len(payload))
        self.assertEqual(meta["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(meta["authority_status"], "NOT_ESTABLISHED_BY_APP")

    def test_invalid_role_and_overlong_revision_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported reference role"):
            build_reference_metadata("crew", "crew.csv", b"x")
        with self.assertRaisesRegex(ValueError, "200 characters"):
            build_reference_metadata("activity", "activity.csv", b"x", "x" * 201)

    def test_metadata_by_role_ignores_unknown_items(self):
        activity = build_reference_metadata("activity", "a.csv", b"a", "R1")
        resource = build_reference_metadata("resource", "r.csv", b"r", "R2")
        indexed = metadata_by_role([activity, {"role": "unknown"}, resource])
        self.assertEqual(set(indexed), {"activity", "resource"})
        self.assertEqual(indexed["activity"]["revision"], "R1")

    def test_reference_review_csv_attaches_metadata_by_role(self):
        checks = [
            {"source_row": 2, "reference_type": "activity", "status": "MATCH", "code": "A-1", "reference_code": "A-1", "reference_unit": "EA", "message": "Exact governed reference match."},
            {"source_row": 3, "reference_type": "resource", "status": "NO_MATCH", "code": "M-1", "reference_code": "", "reference_unit": "", "message": "No match."},
        ]
        activity = build_reference_metadata("activity", "activity.csv", b"activity", "Rev A")
        data = reference_review_csv(checks, [activity])
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        self.assertEqual(rows[0]["reference_filename"], "activity.csv")
        self.assertEqual(rows[0]["reference_revision"], "Rev A")
        self.assertEqual(rows[0]["reference_sha256"], activity["sha256"])
        self.assertEqual(rows[0]["authority_status"], "NOT_ESTABLISHED_BY_APP")
        self.assertEqual(rows[1]["reference_filename"], "")
        self.assertEqual(rows[1]["reference_revision"], "")


if __name__ == "__main__":
    unittest.main()
