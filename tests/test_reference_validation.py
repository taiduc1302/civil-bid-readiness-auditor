from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from reference_validation import (
    build_reference_index,
    canonicalize_export_rows,
    parse_reference_csv,
    validate_code,
    validate_export_rows,
)


class GovernedReferenceValidationTests(unittest.TestCase):
    def read_csv(self, name: str):
        with (ROOT / "samples" / name).open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_exact_resource_match_accepts_safe_uom_alias(self):
        rows = self.read_csv("synthetic_resource_reference.csv")
        index = build_reference_index(rows, "resource_code")
        result = validate_code("EQ-EXC20", "Hours", index)
        self.assertEqual(result["status"], "MATCH")
        self.assertEqual(result["reference_unit"], "HR")

    def test_unit_mismatch_is_reported_without_conversion(self):
        rows = self.read_csv("synthetic_resource_reference.csv")
        index = build_reference_index(rows, "resource_code")
        result = validate_code("M-COMMON", "LCY", index)
        self.assertEqual(result["status"], "UNIT_MISMATCH")
        self.assertIn("no conversion", result["message"])

    def test_unknown_code_fails_closed(self):
        rows = self.read_csv("synthetic_activity_reference.csv")
        index = build_reference_index(rows, "activity_code")
        result = validate_code("NOT-IN-REFERENCE", "M", index)
        self.assertEqual(result["status"], "NO_MATCH")

    def test_blank_code_is_not_checked(self):
        rows = self.read_csv("synthetic_resource_reference.csv")
        index = build_reference_index(rows, "resource_code")
        result = validate_code("", "HR", index)
        self.assertEqual(result["status"], "NOT_CHECKED")

    def test_duplicate_reference_codes_are_rejected(self):
        rows = [
            {"resource_code": "EQ-1", "description": "One", "unit": "HR"},
            {"resource_code": "eq-1", "description": "Duplicate", "unit": "HR"},
        ]
        with self.assertRaisesRegex(ValueError, "Duplicate reference code"):
            build_reference_index(rows, "resource_code")

    def test_empty_reference_index_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no nonblank resource_code"):
            build_reference_index([{"resource_code": "", "unit": "HR"}], "resource_code")

    def test_row_linked_validation_does_not_mutate_source(self):
        rows = [{"__source_row": "42", "Activity Code": "STM300", "Resource Code": "M-PVC300", "Unit": "M"}]
        original = dict(rows[0])
        activity = build_reference_index(self.read_csv("synthetic_activity_reference.csv"), "activity_code")
        resource = build_reference_index(self.read_csv("synthetic_resource_reference.csv"), "resource_code")
        results = validate_export_rows(rows, activity_reference=activity, resource_reference=resource)
        self.assertEqual(rows[0], original)
        self.assertEqual({item["reference_type"] for item in results}, {"activity", "resource"})
        self.assertTrue(all(item["source_row"] == 42 for item in results))
        self.assertTrue(all(item["status"] == "MATCH" for item in results))

    def test_bcy_lcy_and_ton_tonne_remain_distinct(self):
        rows = [
            {"resource_code": "EARTH", "description": "Earth", "unit": "BCY"},
            {"resource_code": "MASS", "description": "Mass", "unit": "TON"},
        ]
        index = build_reference_index(rows, "resource_code")
        self.assertEqual(validate_code("EARTH", "LCY", index)["status"], "UNIT_MISMATCH")
        self.assertEqual(validate_code("MASS", "tonne", index)["status"], "UNIT_MISMATCH")

    def test_reference_csv_requires_explicit_code_and_unit_headers(self):
        good = b"resource_code,description,unit\nEQ-1,Excavator,HR\n"
        rows = parse_reference_csv(good, "resource_code")
        self.assertEqual(rows[0]["resource_code"], "EQ-1")
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            parse_reference_csv(b"description,unit\nExcavator,HR\n", "resource_code")

    def test_reference_csv_rejects_blank_and_header_only_files(self):
        with self.assertRaisesRegex(ValueError, "blank"):
            parse_reference_csv(b"", "activity_code")
        with self.assertRaisesRegex(ValueError, "no reference rows"):
            parse_reference_csv(b"activity_code,unit\n", "activity_code")

    def test_canonicalize_export_rows_uses_explicit_audit_mapping(self):
        sheets = {"Estimate": [{
            "Activity Code": "STM300", "Resource Code": "M-PVC300", "UOM": "M", "__source_row": "17"
        }]}
        mappings = {"Estimate": {"activity": "Activity Code", "resource_code": "Resource Code", "unit": "UOM"}}
        canonical = canonicalize_export_rows(sheets, mappings)
        self.assertEqual(canonical[0]["activity"], "STM300")
        self.assertEqual(canonical[0]["resource_code"], "M-PVC300")
        self.assertEqual(canonical[0]["unit"], "M")
        self.assertEqual(canonical[0]["__source_row"], "17")
        self.assertEqual(canonical[0]["__sheet"], "Estimate")


if __name__ == "__main__":
    unittest.main()
