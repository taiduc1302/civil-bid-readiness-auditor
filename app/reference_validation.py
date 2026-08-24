"""Deterministic validation against explicitly supplied reference/codebook rows.

This module never invents codes or repairs estimate values. It reports whether
exported Activity/Resource codes are found in a governed reference snapshot and
whether explicitly supplied units agree after conservative UOM normalization.
"""
from __future__ import annotations

from typing import Any, Iterable

from audit_engine import normalize_name, normalize_unit


REFERENCE_STATUSES = ("MATCH", "UNIT_MISMATCH", "NO_MATCH", "NOT_CHECKED")


def build_reference_index(rows: Iterable[dict[str, Any]], code_field: str, unit_field: str = "unit") -> dict[str, dict[str, str]]:
    """Build a normalized exact-code index from an explicit reference snapshot."""
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        raw_code = str(row.get(code_field, "") or "").strip()
        if not raw_code:
            continue
        key = normalize_name(raw_code)
        if key in index:
            raise ValueError(f"Duplicate reference code: {raw_code}")
        index[key] = {
            "code": raw_code,
            "description": str(row.get("description", "") or "").strip(),
            "unit": str(row.get(unit_field, "") or "").strip(),
        }
    return index


def validate_code(code: Any, unit: Any, reference_index: dict[str, dict[str, str]]) -> dict[str, str]:
    """Validate one exported code against a governed exact-code reference."""
    raw_code = str(code or "").strip()
    raw_unit = str(unit or "").strip()
    if not raw_code:
        return {"status": "NOT_CHECKED", "code": "", "reference_code": "", "reference_unit": "", "message": "No source code supplied."}

    reference = reference_index.get(normalize_name(raw_code))
    if reference is None:
        return {"status": "NO_MATCH", "code": raw_code, "reference_code": "", "reference_unit": "", "message": "Code is not present in the supplied governed reference."}

    ref_unit = reference.get("unit", "")
    if raw_unit and ref_unit and normalize_unit(raw_unit) != normalize_unit(ref_unit):
        return {
            "status": "UNIT_MISMATCH",
            "code": raw_code,
            "reference_code": reference["code"],
            "reference_unit": ref_unit,
            "message": "Source unit differs from the supplied reference unit; no conversion was attempted.",
        }

    return {
        "status": "MATCH",
        "code": raw_code,
        "reference_code": reference["code"],
        "reference_unit": ref_unit,
        "message": "Exact governed reference match.",
    }


def validate_export_rows(
    rows: Iterable[dict[str, Any]],
    activity_reference: dict[str, dict[str, str]] | None = None,
    resource_reference: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Return row-linked validation records without mutating source rows."""
    results: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=1):
        source_row = int(row.get("__source_row", position))
        unit = row.get("unit", row.get("Unit", ""))
        if activity_reference is not None:
            activity_code = row.get("activity", row.get("Activity Code", ""))
            check = validate_code(activity_code, unit, activity_reference)
            results.append({"source_row": source_row, "reference_type": "activity", **check})
        if resource_reference is not None:
            resource_code = row.get("resource_code", row.get("Resource Code", ""))
            check = validate_code(resource_code, unit, resource_reference)
            results.append({"source_row": source_row, "reference_type": "resource", **check})
    return results
