from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from audit_engine import audit, parse_upload
from finding_review import default_dispositions
from review_delta import compare_review_packages
from review_package import build_review_package


class ReviewDeltaTests(unittest.TestCase):
    def base_session(self):
        sample = ROOT / "samples" / "synthetic_civil_estimate.csv"
        result = audit(parse_upload(sample.name, sample.read_bytes()))
        return {
            "filename": sample.name,
            "result": result,
            "dispositions": default_dispositions(result),
            "mappings": {},
        }

    def package(self, session, filename="snapshot.zip"):
        data, _ = build_review_package(session)
        return filename, data

    def test_identical_packages_are_all_unchanged(self):
        package = self.package(self.base_session())
        result = compare_review_packages(package[0], package[1], package[0], package[1])
        self.assertTrue(result["same_package_sha256"])
        self.assertEqual(result["finding_counts"]["UNCHANGED"], 14)
        self.assertEqual(sum(result["finding_counts"][key] for key in result["finding_counts"] if key != "UNCHANGED"), 0)
        self.assertFalse(result["session_created"])
        self.assertFalse(result["re_audit_performed"])
        self.assertFalse(result["correctness_inferred"])

    def test_review_state_change_is_separate_from_deterministic_evidence(self):
        earlier = self.base_session()
        later = copy.deepcopy(earlier)
        later["dispositions"][1] = {"status": "Reviewed", "reason": "Checked against source."}
        old_package = self.package(earlier, "earlier.zip")
        new_package = self.package(later, "later.zip")
        result = compare_review_packages(old_package[0], old_package[1], new_package[0], new_package[1])
        self.assertEqual(result["finding_counts"]["REVIEW_CHANGED"], 1)
        changed = [row for row in result["finding_changes"] if row["change_type"] == "REVIEW_CHANGED"]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["evidence_fields_changed"], [])
        self.assertEqual(changed[0]["review_fields_changed"], ["status", "reason"])

    def test_deterministic_message_change_is_evidence_change_not_review_change(self):
        earlier = self.base_session()
        later = copy.deepcopy(earlier)
        later["result"]["findings"][0]["message"] += " Updated archived evidence text."
        old_package = self.package(earlier, "earlier.zip")
        new_package = self.package(later, "later.zip")
        result = compare_review_packages(old_package[0], old_package[1], new_package[0], new_package[1])
        self.assertEqual(result["finding_counts"]["EVIDENCE_CHANGED"], 1)
        changed = [row for row in result["finding_changes"] if row["change_type"] == "EVIDENCE_CHANGED"]
        self.assertEqual(changed[0]["evidence_fields_changed"], ["message"])
        self.assertEqual(changed[0]["review_fields_changed"], [])

    def test_reference_result_and_metadata_drift_are_reported_separately(self):
        earlier = self.base_session()
        earlier["reference_results"] = [{
            "sheet": "Synthetic", "source_row": "2", "reference_type": "activity", "status": "NO_MATCH",
            "code": "ACT-001", "reference_code": "", "reference_unit": "", "message": "No exact reference match.",
        }]
        earlier["reference_sources"] = ["activity-a.csv"]
        earlier["reference_metadata"] = [{
            "role": "activity", "filename": "activity-a.csv", "revision": "Rev A", "size_bytes": 12,
            "sha256": "a" * 64, "authority_status": "NOT_ESTABLISHED_BY_APP",
        }]
        later = copy.deepcopy(earlier)
        later["reference_results"][0]["status"] = "MATCH"
        later["reference_results"][0]["reference_code"] = "ACT-001"
        later["reference_results"][0]["reference_unit"] = "ea"
        later["reference_results"][0]["message"] = "Exact reference match."
        later["reference_sources"] = ["activity-b.csv"]
        later["reference_metadata"][0].update({
            "filename": "activity-b.csv", "revision": "Rev B", "size_bytes": 13, "sha256": "b" * 64,
        })
        old_package = self.package(earlier, "earlier.zip")
        new_package = self.package(later, "later.zip")
        result = compare_review_packages(old_package[0], old_package[1], new_package[0], new_package[1])
        self.assertEqual(result["reference_counts"]["CHANGED"], 1)
        self.assertIn("status", result["reference_changes"][0]["fields_changed"])
        self.assertEqual(result["reference_metadata_counts"]["CHANGED"], 1)
        self.assertEqual(result["reference_metadata_changes"][0]["role"], "activity")
        self.assertIn("sha256", result["reference_metadata_changes"][0]["fields_changed"])

    def test_duplicate_finding_anchor_fails_closed(self):
        earlier = self.base_session()
        later = copy.deepcopy(earlier)
        duplicate = copy.deepcopy(later["result"]["findings"][0])
        duplicate["id"] = max(item["id"] for item in later["result"]["findings"]) + 1
        later["result"]["findings"].append(duplicate)
        later["result"]["counts"][duplicate["severity"]] += 1
        later["result"]["review_metrics"]["finding_count"] += 1
        later["dispositions"][duplicate["id"]] = {"status": "Open", "reason": ""}
        old_package = self.package(earlier, "earlier.zip")
        new_package = self.package(later, "later.zip")
        with self.assertRaisesRegex(ValueError, "duplicate anchor"):
            compare_review_packages(old_package[0], old_package[1], new_package[0], new_package[1])


if __name__ == "__main__":
    unittest.main()
