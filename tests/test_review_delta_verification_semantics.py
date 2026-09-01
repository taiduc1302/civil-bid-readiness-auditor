from __future__ import annotations

import copy
import io
import json
import sys
import unittest
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
    delta_export_manifest,
    verify_review_delta_export,
)
from review_package import build_review_package


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


class ReviewDeltaVerificationSemanticTests(unittest.TestCase):
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
            "earlier.zip", build_review_package(earlier)[0],
            "later.zip", build_review_package(later)[0],
        )
        return build_review_delta_export(comparison)[0]

    def members(self):
        with zipfile.ZipFile(io.BytesIO(self.bundle())) as book:
            return {name: book.read(name) for name in book.namelist()}

    def make_rehashed_zip(self, members):
        members = dict(members)
        members.pop("integrity.json", None)
        members["integrity.json"] = _json_bytes(delta_export_integrity(members))
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as book:
            for name, payload in members.items():
                book.writestr(name, payload)
        return output.getvalue()

    def test_rehashed_summary_counts_cannot_disagree_with_change_rows(self):
        members = self.members()
        comparison = json.loads(members["review_delta.json"])
        comparison["finding_counts"]["UNCHANGED"] += 1
        members["review_delta.json"] = _json_bytes(comparison)
        members["manifest.json"] = _json_bytes(delta_export_manifest(comparison))
        with self.assertRaisesRegex(ValueError, "finding_counts do not match"):
            verify_review_delta_export(self.make_rehashed_zip(members))

    def test_rehashed_duplicate_finding_anchor_fails_before_csv_agreement(self):
        members = self.members()
        comparison = json.loads(members["review_delta.json"])
        duplicate = copy.deepcopy(comparison["finding_changes"][0])
        comparison["finding_changes"].append(duplicate)
        comparison["finding_counts"][duplicate["change_type"]] += 1
        members["review_delta.json"] = _json_bytes(comparison)
        members["manifest.json"] = _json_bytes(delta_export_manifest(comparison))
        with self.assertRaisesRegex(ValueError, "duplicate finding anchor"):
            verify_review_delta_export(self.make_rehashed_zip(members))

    def test_rehashed_unknown_change_type_fails_closed(self):
        members = self.members()
        comparison = json.loads(members["review_delta.json"])
        comparison["finding_changes"][0]["change_type"] = "BETTER"
        members["review_delta.json"] = _json_bytes(comparison)
        members["manifest.json"] = _json_bytes(delta_export_manifest(comparison))
        with self.assertRaisesRegex(ValueError, "unsupported finding change type"):
            verify_review_delta_export(self.make_rehashed_zip(members))


if __name__ == "__main__":
    unittest.main()
