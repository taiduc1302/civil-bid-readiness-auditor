"""Optional governed checks for explicitly exported Crew Code / Production Rate values.

This module is evidence-only. It never fills missing values, proposes crews,
calculates production, or treats historical cost/rate data as current authority.
"""
from __future__ import annotations

import csv
import hashlib
import io
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
MAX_OPERATIONAL_REFERENCE_BYTES = 5 * 1024 * 1024
_OPERATIONAL_HEADERS = {
    "activity_code": ("activity_code", "activity code", "activity", "activity id"),
    "crew_code": ("crew_code", "crew code", "crew", "crew id"),
    "production_rate": ("production_rate", "production rate", "prod rate", "prod. rate"),
}


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


def _header_map(headers: Iterable[str]) -> dict[str, str]:
    lookup = {normalize_name(header): str(header) for header in headers if str(header).strip()}
    mapped: dict[str, str] = {}
    for field, candidates in _OPERATIONAL_HEADERS.items():
        for candidate in candidates:
            source = lookup.get(normalize_name(candidate))
            if source is not None:
                mapped[field] = source
                break
    return mapped


def parse_operational_reference_csv(data: bytes) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    """Parse explicit Activity/Crew/Production reference evidence without inference.

    Activity Code is required. At least one Crew Code or Production Rate column is
    required, and at least one row must contain an explicit operational value.
    Extra columns, including historical cost/rate fields, are ignored.
    """
    payload = bytes(data)
    if not payload.strip():
        raise ValueError("Operational reference CSV is blank.")
    if len(payload) > MAX_OPERATIONAL_REFERENCE_BYTES:
        raise ValueError("Operational reference CSV exceeds the 5 MB local processing limit.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Operational reference CSV must be UTF-8 encoded.") from exc
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
        mapped = _header_map(headers)
        if "activity_code" not in mapped:
            raise ValueError("Operational reference CSV is missing required Activity Code column.")
        available = tuple(field for field in ("crew_code", "production_rate") if field in mapped)
        if not available:
            raise ValueError("Operational reference CSV must include Crew Code and/or Production Rate.")
        rows: list[dict[str, str]] = []
        explicit_operational_value = False
        for source in reader:
            row = {
                "activity_code": _text(source.get(mapped["activity_code"], "")),
                "crew_code": _text(source.get(mapped.get("crew_code", ""), "")) if "crew_code" in mapped else "",
                "production_rate": _text(source.get(mapped.get("production_rate", ""), "")) if "production_rate" in mapped else "",
            }
            if row["crew_code"] or row["production_rate"]:
                explicit_operational_value = True
            rows.append(row)
    except csv.Error as exc:
        raise ValueError(f"Operational reference CSV could not be read: {exc}") from exc
    if not rows:
        raise ValueError("Operational reference CSV has a header but no reference rows.")
    if not any(row["activity_code"] for row in rows):
        raise ValueError("Operational reference contains no Activity Codes.")
    if not explicit_operational_value:
        raise ValueError("Operational reference contains no explicit Crew Code or Production Rate values.")
    return rows, available


def build_operational_reference_metadata(filename: str, data: bytes, revision: str = "") -> dict[str, Any]:
    """Record immutable upload evidence without claiming reference authority."""
    name = _text(filename)
    if not name:
        raise ValueError("Operational reference filename is required.")
    label = _text(revision)
    if len(label) > 200:
        raise ValueError("Operational reference revision/label must be 200 characters or fewer.")
    payload = bytes(data)
    return {
        "role": "operational_activity",
        "filename": name,
        "revision": label,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "authority_status": "NOT_ESTABLISHED_BY_APP",
    }


def build_activity_operational_index(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Build an exact Activity Code index from an explicitly supplied reference snapshot."""
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
        results.append({"sheet": str(row.get("__sheet", "")), "source_row": source_row, **result})
    return results
