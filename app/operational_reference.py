"""Optional governed checks for explicitly exported Crew Code / Production Rate values.

This module is evidence-only. It never fills missing values, proposes crews,
calculates production, or treats historical cost/rate data as current authority.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from audit_engine import normalize_name


OPERATIONAL_STATUSES = (
    "MATCH",
    "CREW_MISMATCH",
    "PRODUCTION_MISMATCH",
    "CREW_AND_PRODUCTION_MISMATCH",
    "INVALID_PRODUCTION_RATE",
    "NO_MATCH",
    "NOT_CHECKED",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite_decimal(value: Any) -> Decimal | None:
    text = _text(value).replace(",", "")
    if not text:
        return None
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def build_activity_operational_index(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Build an exact Activity Code index from an explicitly approved reference snapshot."""
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        activity_code = _text(row.get("activity_code"))
        if not activity_code:
            continue
        key = normalize_name(activity_code)
        if key in index:
            raise ValueError(f"Duplicate activity reference code: {activity_code}")
        index[key] = {
            "activity_code": activity_code,
            "crew_code": _text(row.get("crew_code")),
            "production_rate": _text(row.get("production_rate")),
        }
    if not index:
        raise ValueError("Operational reference contains no Activity Codes.")
    return index


def validate_operational_fields(
    activity_code: Any,
    crew_code: Any,
    production_rate: Any,
    reference_index: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Compare only fields explicitly present on both source and reference rows."""
    source_activity = _text(activity_code)
    source_crew = _text(crew_code)
    source_prod_raw = _text(production_rate)
    if not source_activity:
        return {
            "status": "NOT_CHECKED",
            "activity_code": "",
            "reference_activity_code": "",
            "crew_code": source_crew,
            "reference_crew_code": "",
            "production_rate": source_prod_raw,
            "reference_production_rate": "",
            "message": "No source Activity Code supplied; no operational values were inferred.",
        }

    reference = reference_index.get(normalize_name(source_activity))
    if reference is None:
        return {
            "status": "NO_MATCH",
            "activity_code": source_activity,
            "reference_activity_code": "",
            "crew_code": source_crew,
            "reference_crew_code": "",
            "production_rate": source_prod_raw,
            "reference_production_rate": "",
            "message": "Activity Code is not present in the supplied governed operational reference.",
        }

    ref_crew = reference["crew_code"]
    ref_prod_raw = reference["production_rate"]
    comparable_crew = bool(source_crew and ref_crew)
    comparable_prod = bool(source_prod_raw and ref_prod_raw)
    if not comparable_crew and not comparable_prod:
        return {
            "status": "NOT_CHECKED",
            "activity_code": source_activity,
            "reference_activity_code": reference["activity_code"],
            "crew_code": source_crew,
            "reference_crew_code": ref_crew,
            "production_rate": source_prod_raw,
            "reference_production_rate": ref_prod_raw,
            "message": "No Crew Code or Production Rate was explicitly present on both source and reference; nothing was inferred.",
        }

    crew_mismatch = comparable_crew and normalize_name(source_crew) != normalize_name(ref_crew)
    production_mismatch = False
    if comparable_prod:
        source_prod = _finite_decimal(source_prod_raw)
        ref_prod = _finite_decimal(ref_prod_raw)
        if source_prod is None or ref_prod is None:
            return {
                "status": "INVALID_PRODUCTION_RATE",
                "activity_code": source_activity,
                "reference_activity_code": reference["activity_code"],
                "crew_code": source_crew,
                "reference_crew_code": ref_crew,
                "production_rate": source_prod_raw,
                "reference_production_rate": ref_prod_raw,
                "message": "Production Rate comparison requires finite explicit numeric values; no replacement was inferred.",
            }
        production_mismatch = source_prod != ref_prod

    if crew_mismatch and production_mismatch:
        status = "CREW_AND_PRODUCTION_MISMATCH"
        message = "Crew Code and Production Rate differ from the supplied governed reference."
    elif crew_mismatch:
        status = "CREW_MISMATCH"
        message = "Crew Code differs from the supplied governed reference."
    elif production_mismatch:
        status = "PRODUCTION_MISMATCH"
        message = "Production Rate differs from the supplied governed reference."
    else:
        status = "MATCH"
        message = "All explicitly comparable operational fields match the supplied governed reference."

    return {
        "status": status,
        "activity_code": source_activity,
        "reference_activity_code": reference["activity_code"],
        "crew_code": source_crew,
        "reference_crew_code": ref_crew,
        "production_rate": source_prod_raw,
        "reference_production_rate": ref_prod_raw,
        "message": message,
    }


def validate_operational_export_rows(
    rows: Iterable[dict[str, Any]],
    reference_index: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Return row-linked operational evidence without mutating export rows."""
    results: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=1):
        source_row = int(row.get("__source_row", position))
        result = validate_operational_fields(
            row.get("activity", row.get("Activity Code", "")),
            row.get("crew_code", row.get("Crew Code", "")),
            row.get("production_rate", row.get("Production Rate", "")),
            reference_index,
        )
        results.append({"source_row": source_row, **result})
    return results
