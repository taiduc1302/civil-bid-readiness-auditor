from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from operational_reference import (
    build_activity_operational_index,
    validate_operational_export_rows,
    validate_operational_fields,
)


class OperationalReferenceTests(unittest.TestCase):
    def index(self):
        return build_activity_operational_index([
            {"activity_code": "STM300", "crew_code": "CR-PIPE", "production_rate": "5.0", "historical_cost": "999"},
            {"activity_code": "EXC", "crew_code": "CR-EARTH", "production_rate": "12", "historical_cost": "123"},
        ])

    def test_exact_explicit_operational_match(self):
        result = validate_operational_fields("STM300", "cr-pipe", "5.00", self.index())
        self.assertEqual(result["status"], "MATCH")

    def test_missing_source_operational_fields_are_not_filled(self):
        result = validate_operational_fields("STM300", "", "", self.index())
        self.assertEqual(result["status"], "NOT_CHECKED")
        self.assertEqual(result["crew_code"], "")
        self.assertEqual(result["production_rate"], "")
        self.assertIn("nothing was inferred", result["message"])

    def test_crew_mismatch_is_evidence_only(self):
        result = validate_operational_fields("STM300", "OTHER-CREW", "5", self.index())
        self.assertEqual(result["status"], "CREW_MISMATCH")
        self.assertEqual(result["reference_crew_code"], "CR-PIPE")

    def test_production_mismatch_is_evidence_only(self):
        result = validate_operational_fields("STM300", "CR-PIPE", "6", self.index())
        self.assertEqual(result["status"], "PRODUCTION_MISMATCH")
        self.assertEqual(result["reference_production_rate"], "5.0")

    def test_both_mismatches_are_explicit(self):
        result = validate_operational_fields("STM300", "OTHER", "6", self.index())
        self.assertEqual(result["status"], "CREW_AND_PRODUCTION_MISMATCH")

    def test_nonfinite_or_nonnumeric_production_is_invalid_not_repaired(self):
        for value in ("NaN", "Infinity", "five"):
            with self.subTest(value=value):
                result = validate_operational_fields("STM300", "CR-PIPE", value, self.index())
                self.assertEqual(result["status"], "INVALID_PRODUCTION_RATE")
                self.assertEqual(result["production_rate"], value)

    def test_unknown_activity_fails_closed(self):
        result = validate_operational_fields("UNKNOWN", "CR-X", "1", self.index())
        self.assertEqual(result["status"], "NO_MATCH")

    def test_duplicate_activity_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate activity reference code"):
            build_activity_operational_index([
                {"activity_code": "EXC", "crew_code": "A", "production_rate": "1"},
                {"activity_code": "exc", "crew_code": "B", "production_rate": "2"},
            ])

    def test_historical_cost_fields_are_ignored(self):
        index = self.index()
        self.assertEqual(set(index["stm300"]), {"activity_code", "crew_code", "production_rate"})

    def test_row_linkage_is_preserved_and_source_not_mutated(self):
        rows = [{"Activity Code": "EXC", "Crew Code": "CR-EARTH", "Production Rate": "12", "__source_row": "42"}]
        original = dict(rows[0])
        results = validate_operational_export_rows(rows, self.index())
        self.assertEqual(rows[0], original)
        self.assertEqual(results[0]["source_row"], 42)
        self.assertEqual(results[0]["status"], "MATCH")


if __name__ == "__main__":
    unittest.main()
