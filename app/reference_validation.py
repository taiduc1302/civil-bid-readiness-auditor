"""Deterministic validation against explicitly supplied reference/codebook rows.

This module never invents codes or repairs estimate values. It reports whether
exported Activity/Resource codes are found in a governed reference snapshot and
whether explicitly supplied units agree after conservative UOM normalization.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from audit_engine import normalize_name, normalize_unit


REFERENCE_STATUSES = ("MATCH", "UNIT_MISMATCH", "NO_MATCH", "NOT_CHECKED")
MAX_REFERENCE_BYTES = 5 * 1024 * 1024


def parse_reference_csv(data: bytes, code_field: str) -> list[dict[str, str]]:
    """Parse a small UTF-8 governed reference CSV with explicit code/unit columns."""
    if not data.strip():
        raise ValueError("Reference CSV is blank.")
    if len(data) > MAX_REFERENCE_BYTES:
        raise ValueError("Reference CSV exceeds the 5 MB local processing limit.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Reference CSV must be UTF-8 encoded.") from exc
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
        normalized = {normalize_name(header): header for header in headers if header}
        required = {normalize_name(code_field), "unit"}
        missing = [name for name in required if name not in normalized]
        if missing:
            raise ValueError(f"Reference CSV is missing required columns: {', '.join(sorted(missing))}")
        rows = [{str(k or "").strip(): str(v or "").strip() for k, v in row.items()} for row in reader]
    except csv.Error as exc:
        raise ValueError(f"Reference CSV could not be read: {exc}") from exc
    if not rows:
        raise ValueError("Reference CSV has a header but no reference rows.")
    return rows


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
    if not index:
        raise ValueError(f"Reference contains no nonblank {code_field} values.")
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


def canonicalize_export_rows(
    sheets: dict[str, list[dict[str, str]]], mappings: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    """Create non-mutating canonical rows from the same explicit mappings used by the audit."""
    rows: list[dict[str, str]] = []
    for sheet, source_rows in sheets.items():
        mapping = mappings.get(sheet, {})
        for position, source in enumerate(source_rows, start=2):
            canonical = {field: source.get(column, "") for field, column in mapping.items() if column}
            canonical["__source_row"] = source.get("__source_row", str(position))
            canonical["__sheet"] = sheet
            rows.append(canonical)
    return rows


def validate_export_rows(
    rows: Iterable[dict[str, Any]],
    activity_reference: dict[str, dict[str, str]] | None = None,
    resource_reference: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Return row-linked validation records without mutating source rows."""
    results: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=1):
        source_row = int(row.get("__source_row", position))
        sheet = str(row.get("__sheet", ""))
        unit = row.get("unit", row.get("Unit", ""))
        if activity_reference is not None:
            activity_code = row.get("activity", row.get("Activity Code", ""))
            check = validate_code(activity_code, unit, activity_reference)
            results.append({"sheet": sheet, "source_row": source_row, "reference_type": "activity", **check})
        if resource_reference is not None:
            resource_code = row.get("resource_code", row.get("Resource Code", ""))
            check = validate_code(resource_code, unit, resource_reference)
            results.append({"sheet": sheet, "source_row": source_row, "reference_type": "resource", **check})
    return results


def reference_results_csv(results: Iterable[dict[str, Any]]) -> bytes:
    """Export reference checks safely for spreadsheet review."""
    fields = ["sheet", "source_row", "reference_type", "status", "code", "reference_code", "reference_unit", "message"]

    def safe(value: Any) -> str:
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for item in results:
        writer.writerow({field: safe(item.get(field, "")) for field in fields})
    return out.getvalue().encode("utf-8")
