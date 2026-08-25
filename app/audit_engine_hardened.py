"""Compatibility layer that hardens CSV ingestion and rule-specific hierarchy context.

The consolidated audit implementation remains preserved in ``audit_engine_legacy``.
This module re-exports its public API, overrides CSV parsing with the same controlled
header-scan policy used by XLSX, and narrows duplicate/conflict grouping according
to each rule's semantic level.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import audit_engine_legacy as _legacy
from audit_engine_legacy import *  # noqa: F401,F403 - compatibility re-export


def parse_csv_bytes(data: bytes, name: str = "upload.csv") -> dict[str, list[dict[str, str]]]:
    """Parse UTF-8 CSV with controlled early-row header detection.

    The first ``HEADER_SCAN_ROWS`` physical rows are scored with the same alias
    policy as XLSX. If confidence is below the existing threshold, the first
    readable row remains the header so manual mapping stays possible. Original
    physical row numbers are retained in ``__source_row``.
    """
    if not data.strip():
        raise InputError("The CSV file is blank. Export at least a header row and one estimate row.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise InputError("CSV exceeds the 25 MB local processing limit.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError("CSV must be UTF-8 encoded.") from exc

    try:
        sparse_rows = [(row_number, [str(value or "") for value in values]) for row_number, values in enumerate(csv.reader(io.StringIO(text)), start=1)]
    except csv.Error as exc:
        raise InputError(f"CSV could not be read: {exc}") from exc
    if not sparse_rows or not any(any(value.strip() for value in values) for _, values in sparse_rows):
        raise InputError("CSV has no header row.")

    header_index = _legacy._detect_header_index(sparse_rows)
    headers = [value.strip() for value in sparse_rows[header_index][1]]
    if not any(headers):
        raise InputError("CSV has no header row.")

    rows: list[dict[str, str]] = []
    for source_row, source in sparse_rows[header_index + 1:]:
        record = {
            headers[index]: (source[index].strip() if index < len(source) else "")
            for index in range(len(headers))
            if headers[index]
        }
        if any(record.values()):
            record["__source_row"] = str(source_row)
            rows.append(record)
    if not rows:
        raise InputError("CSV has a header but no estimate rows.")
    return {Path(name).stem or "CSV": rows}


def parse_upload(filename: str, data: bytes) -> dict[str, list[dict[str, str]]]:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".csv":
        return parse_csv_bytes(data, filename)
    if suffix == ".xlsx":
        return _legacy.parse_xlsx_bytes(data)
    raise InputError("Supported file types are .csv and .xlsx. Legacy .xls, PDFs, images, and macros are unsupported.")


def _duplicate_context(values: dict[str, str]) -> tuple[str, str, str, str]:
    """Resource-level identity used by exact duplicate detection (R008)."""
    return tuple(_legacy.normalize_name(values.get(field)) for field in ("bid_item", "activity", "resource_type", "resource_code"))


def _conflict_context(values: dict[str, str]) -> tuple[str, str, str]:
    """Scope context used by R009/R010 without hiding conflicts behind Resource Code."""
    return tuple(_legacy.normalize_name(values.get(field)) for field in ("bid_item", "activity", "resource_type"))


def audit(sheets: dict[str, list[dict[str, str]]], mappings: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """Audit parsed records with rule-specific hierarchy grouping."""
    findings: list[Finding] = []
    finding_id = 0

    def add(severity: str, rule_id: str, sheet: str, row: int, field: str, message: str, evidence: Any, action: str) -> None:
        nonlocal finding_id
        finding_id += 1
        findings.append(Finding(finding_id, severity, rule_id, sheet, row, field, message, str(evidence), action))

    all_rows: list[tuple[str, int, dict[str, str], dict[str, str]]] = []
    missing_mappings: list[str] = []
    for sheet, rows in sheets.items():
        headers = [header for header in list(rows[0]) if not header.startswith("__")] if rows else []
        detected = column_map(headers)
        supplied = (mappings or {}).get(sheet, {})
        map_for_sheet = {**detected, **{field: column for field, column in supplied.items() if column}}
        missing = [field for field in REQUIRED_FIELDS if not map_for_sheet.get(field)]
        if missing:
            missing_mappings.append(f"{sheet}: {', '.join(missing)}")
            continue
        for index, original in enumerate(rows, start=2):
            source_row = int(original.get("__source_row", index))
            canonical = {field: original.get(column, "") for field, column in map_for_sheet.items()}
            all_rows.append((sheet, source_row, original, canonical))
    if missing_mappings:
        raise InputError("Required columns could not be mapped: " + "; ".join(missing_mappings))
    if not all_rows:
        raise InputError("No auditable rows were found after mapping columns.")

    description_groups: dict[tuple[str, tuple[str, str, str]], list[tuple[str, int, dict[str, str]]]] = defaultdict(list)
    duplicate_keys: dict[tuple[Any, ...], list[tuple[str, int]]] = defaultdict(list)
    category_amounts: Counter[str] = Counter()
    total_amount = Decimal("0")
    for sheet, row, original, values in all_rows:
        desc = values.get("description", "").strip()
        qty = _legacy.number(values.get("quantity"))
        rate = _legacy.number(values.get("rate"))
        amount = _legacy.number(values.get("amount"))
        unit = values.get("unit", "").strip()
        normalized_unit = _legacy.normalize_unit(unit)
        if not desc:
            add("Critical", "R001", sheet, row, "description", "Description is blank.", "", "Supply an item description and confirm scope with a reviewer.")
        if qty is None:
            add("High", "R002", sheet, row, "quantity", "Quantity is blank or nonnumeric.", values.get("quantity", ""), "Enter or verify the quantity.")
        elif qty == 0:
            add("High", "R003", sheet, row, "quantity", "Quantity is zero.", qty, "Confirm zero is intentional or correct it.")
        elif qty < 0:
            add("High", "R006", sheet, row, "quantity", "Quantity is negative.", qty, "Confirm credit/return treatment with a reviewer.")
        if not unit:
            add("Medium", "R007", sheet, row, "unit", "Unit is blank.", "", "Enter or verify the unit.")
        if rate is None:
            add("High", "R004", sheet, row, "rate", "Rate is blank or nonnumeric.", values.get("rate", ""), "Enter or verify the rate.")
        elif rate == 0:
            add("High", "R005", sheet, row, "rate", "Rate is zero.", rate, "Confirm zero rate is intentional or correct it.")
        elif rate < 0:
            add("High", "R006", sheet, row, "rate", "Rate is negative.", rate, "Confirm credit/return treatment with a reviewer.")
        if amount is not None:
            total_amount += amount
            if amount < 0:
                add("High", "R006", sheet, row, "amount", "Amount is negative.", amount, "Confirm credit/return treatment with a reviewer.")
            if qty is not None and rate is not None and abs((qty * rate) - amount) > Decimal("0.01"):
                add("High", "R011", sheet, row, "amount", "Amount does not equal quantity × rate within $0.01.", f"{qty} × {rate} = {qty * rate}; amount = {amount}", "Reconcile the extension or rounding policy.")
            category = _legacy.normalize_name(values.get("category"))
            if category and amount > 0:
                category_amounts[category] += amount
        for field, value in original.items():
            if field.startswith("__"):
                continue
            if _legacy._safe_formula_text(value):
                add("Low", "R013", sheet, row, field, "Text starts with a formula-like character.", value, "Preserve as text and review before spreadsheet export.")
        if desc:
            duplicate_context = _duplicate_context(values)
            conflict_context = _conflict_context(values)
            description_groups[(_legacy.normalize_name(desc), conflict_context)].append((sheet, row, values))
            duplicate_keys[(_legacy.normalize_name(desc), duplicate_context, normalized_unit, str(qty), str(rate))].append((sheet, row))
        markup = _legacy.number(values.get("markup_pct"), percent=True)
        margin = _legacy.number(values.get("margin_pct"), percent=True)
        for optional_field, parsed in (("amount", amount), ("markup_pct", markup), ("margin_pct", margin)):
            raw = values.get(optional_field, "").strip()
            if raw and parsed is None:
                add("High", "R017", sheet, row, optional_field, "Optional numeric field is not a finite decimal.", raw, "Use a finite decimal value or leave the optional field blank.")
        if markup is not None and margin is not None:
            denominator = Decimal("1") + markup
            if denominator == 0:
                add("High", "R016", sheet, row, "markup_pct", "Markup of -100% has no defined margin conversion.", f"markup {markup}; margin {margin}", "Correct or clear the markup/margin values before review.")
            elif abs((markup / denominator) - margin) > Decimal("0.001"):
                add("High", "R012", sheet, row, "markup_pct/margin_pct", "Markup and margin values do not match the standard conversion.", f"markup {markup}; margin {margin}", "Verify labels and calculation with a reviewer.")

    for key, locations in duplicate_keys.items():
        if len(locations) > 1:
            for sheet, row in locations:
                add("Medium", "R008", sheet, row, "description", "Exact duplicate item key detected within the same estimate context.", f"{key[0]} at {locations}", "Confirm the repeat is intended or remove the duplicate.")
    for (desc, hierarchy), group in description_groups.items():
        signatures = {(_legacy.normalize_unit(v.get("unit")), str(_legacy.number(v.get("quantity"))), str(_legacy.number(v.get("rate")))) for _, _, v in group}
        units = {_legacy.normalize_unit(v.get("unit")) for _, _, v in group if v.get("unit", "").strip()}
        context_label = ", ".join(value for value in hierarchy if value) or "no hierarchy supplied"
        if len(group) > 1 and len(signatures) > 1:
            for sheet, row, _ in group:
                add("High", "R009", sheet, row, "description", "Same description has conflicting values within the same estimate context.", f"{desc}; context: {context_label}", "Confirm the lines represent distinct scope and values.")
        if len(units) > 1:
            for sheet, row, _ in group:
                add("High", "R010", sheet, row, "unit", "Same description uses inconsistent units within the same estimate context.", ", ".join(sorted(units)), "Confirm scope segmentation and units.")
    if total_amount > 0:
        for category, value in category_amounts.items():
            if value / total_amount > Decimal("0.80"):
                add("Medium", "R014", "Summary", 0, "category", "One category exceeds 80% of supplied amount.", f"{category}: {value / total_amount:.1%}", "Check concentration and category classification.")

    rate_peers: dict[tuple[str, str], list[tuple[str, int, Decimal]]] = defaultdict(list)
    for sheet, row, _, values in all_rows:
        rate = _legacy.number(values.get("rate"))
        peer = _legacy._peer_key(values)
        if rate is not None and rate > 0 and peer[0]:
            rate_peers[peer].append((sheet, row, rate))
    for (unit, resource_class), peers in rate_peers.items():
        if len(peers) < 4:
            continue
        positive_rates = sorted(rate for _, _, rate in peers)
        midpoint = len(positive_rates) // 2
        median = (positive_rates[midpoint - 1] + positive_rates[midpoint]) / 2 if len(positive_rates) % 2 == 0 else positive_rates[midpoint]
        if median <= 0:
            continue
        for sheet, row, rate in peers:
            if rate > median * 10 or rate < median / 10:
                peer_label = f"unit {unit}" + (f", class {resource_class}" if resource_class else "")
                add("Medium", "R015", sheet, row, "rate", "Rate is an order-of-magnitude outlier versus comparable rows in this file.", f"rate {rate}; peer median {median}; {peer_label}", "Check units, decimal placement, resource/category class, and source rate. This is not a correctness judgement.")

    counts = Counter(finding.severity for finding in findings)
    score = max(0, 100 - sum(SEVERITY_WEIGHT[finding.severity] for finding in findings))
    affected_locations = {(finding.sheet, finding.row) for finding in findings if finding.row > 0}
    priority_locations = {(finding.sheet, finding.row) for finding in findings if finding.row > 0 and finding.severity in ("Critical", "High")}
    rows_reviewed = len(all_rows)
    affected_rows = len(affected_locations)
    affected_percent = round((affected_rows / rows_reviewed * 100), 2) if rows_reviewed else 0.0
    if counts.get("Critical", 0):
        review_status = "Critical review required"
    elif counts.get("High", 0):
        review_status = "High-priority review required"
    elif counts.get("Medium", 0):
        review_status = "Review recommended"
    elif counts.get("Low", 0):
        review_status = "Minor review prompts"
    else:
        review_status = "No deterministic findings"
    review_metrics = {
        "status": review_status,
        "finding_count": len(findings),
        "affected_rows": affected_rows,
        "affected_row_percent": affected_percent,
        "priority_rows": len(priority_locations),
        "summary_findings": sum(1 for finding in findings if finding.row == 0),
    }
    return {
        "findings": [finding.to_dict() for finding in findings],
        "counts": {severity: counts.get(severity, 0) for severity in ("Critical", "High", "Medium", "Low")},
        "score": score,
        "rows_reviewed": rows_reviewed,
        "sheets_reviewed": sorted(sheets),
        "review_metrics": review_metrics,
        "score_explanation": "Legacy review-status score: 100 minus 20 per Critical, 10 per High, 5 per Medium, and 2 per Low finding; never below 0. Use affected-row and severity metrics as the primary review indicators. Neither measure validates bid correctness or readiness.",
    }
