"""Deterministic, local-only checks for civil estimate exports.

This module deliberately identifies review prompts, not correct bid values or scope.
"""
from __future__ import annotations

import csv
import html
import io
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


REQUIRED_FIELDS = ("description", "quantity", "unit", "rate")
OPTIONAL_FIELDS = ("amount", "category", "markup_pct", "margin_pct")
ALIASES = {
    "description": ("description", "item", "item description", "bid item", "scope"),
    "quantity": ("quantity", "qty", "quantity total"),
    "unit": ("unit", "uom", "unit of measure"),
    "rate": ("rate", "unit rate", "price", "unit price"),
    "amount": ("amount", "total", "extended amount", "cost"),
    "category": ("category", "cost category", "type"),
    "markup_pct": ("markup", "markup %", "markup pct"),
    "margin_pct": ("margin", "margin %", "margin pct"),
}
SEVERITY_WEIGHT = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_XLSX_ENTRIES = 200


class InputError(ValueError):
    """A safe, actionable input error for the local interface."""


@dataclass(frozen=True)
class Finding:
    id: int
    severity: str
    rule_id: str
    sheet: str
    row: int
    field: str
    message: str
    evidence: str
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def number(value: Any, percent: bool = False) -> Decimal | None:
    """Parse only finite decimals; NaN and infinity are deliberately unsupported."""
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    text = text.replace(",", "").replace("$", "").replace("£", "").replace("€", "")
    has_percent = text.endswith("%")
    if has_percent:
        text = text[:-1]
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    if not result.is_finite():
        return None
    if percent and (has_percent or abs(result) > 1):
        return result / Decimal("100")
    return result


def column_map(headers: list[str]) -> dict[str, str]:
    lookup = {normalize_name(header): header for header in headers if str(header).strip()}
    mapped: dict[str, str] = {}
    for field, names in ALIASES.items():
        for candidate in names:
            if candidate in lookup:
                mapped[field] = lookup[candidate]
                break
    return mapped


def parse_csv_bytes(data: bytes, name: str = "upload.csv") -> dict[str, list[dict[str, str]]]:
    if not data.strip():
        raise InputError("The CSV file is blank. Export at least a header row and one estimate row.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise InputError("CSV exceeds the 25 MB local processing limit.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError("CSV must be UTF-8 encoded.") from exc
    try:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise InputError("CSV has no header row.")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            record = {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}
            record["__source_row"] = str(row_number)
            rows.append(record)
    except csv.Error as exc:
        raise InputError(f"CSV could not be read: {exc}") from exc
    if not rows:
        raise InputError("CSV has a header but no estimate rows.")
    return {Path(name).stem or "CSV": rows}


def _column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref)
    if not letters:
        return 0
    value = 0
    for char in letters.group(0):
        value = value * 26 + ord(char) - 64
    return value - 1


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(cell.itertext()).strip()
    value = cell.find(f"{NS_MAIN}v")
    text = "" if value is None or value.text is None else value.text
    if cell_type == "s":
        try:
            return shared[int(text)]
        except (ValueError, IndexError):
            return ""
    return text


def parse_xlsx_bytes(data: bytes) -> dict[str, list[dict[str, str]]]:
    if not data.strip():
        raise InputError("The XLSX file is blank.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise InputError("XLSX exceeds the 25 MB local processing limit.")
    try:
        book = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise InputError("File is not a readable XLSX workbook.") from exc
    try:
        names = set(book.namelist())
        infos = book.infolist()
        if len(infos) > MAX_XLSX_ENTRIES or sum(info.file_size for info in infos) > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise InputError("XLSX exceeds safe local workbook limits.")
        if "xl/workbook.xml" not in names:
            raise InputError("Workbook is missing XLSX workbook metadata.")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in root.findall(f"{NS_MAIN}si")]
        rel_root = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        rels = {r.attrib.get("Id"): r.attrib.get("Target", "") for r in rel_root.findall(f"{NS_PKG}Relationship")}
        wb_root = ET.fromstring(book.read("xl/workbook.xml"))
        sheets: dict[str, list[dict[str, str]]] = {}
        for sheet in wb_root.findall(f".//{NS_MAIN}sheet"):
            sheet_name = sheet.attrib.get("name", "Sheet")
            rid = sheet.attrib.get(f"{NS_REL}id")
            target = rels.get(rid, "")
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            if target not in names:
                continue
            root = ET.fromstring(book.read(target))
            sparse_rows: list[tuple[int, list[str]]] = []
            for row in root.findall(f".//{NS_MAIN}sheetData/{NS_MAIN}row"):
                values: list[str] = []
                for cell in row.findall(f"{NS_MAIN}c"):
                    index = _column_index(cell.attrib.get("r", "A1"))
                    while len(values) <= index:
                        values.append("")
                    values[index] = _cell_text(cell, shared)
                sparse_rows.append((int(row.attrib.get("r", "0")) or len(sparse_rows) + 1, values))
            if not sparse_rows:
                continue
            headers = [item.strip() for item in sparse_rows[0][1]]
            if not any(headers):
                continue
            rows: list[dict[str, str]] = []
            for source_row, source in sparse_rows[1:]:
                record = {headers[i]: source[i].strip() if i < len(source) else "" for i in range(len(headers)) if headers[i]}
                if any(record.values()):
                    record["__source_row"] = str(source_row)
                    rows.append(record)
            if rows:
                sheets[sheet_name] = rows
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise InputError("XLSX has unsupported or malformed workbook XML.") from exc
    finally:
        book.close()
    if not sheets:
        raise InputError("XLSX has no readable sheet with a header and estimate rows.")
    return sheets


def parse_upload(filename: str, data: bytes) -> dict[str, list[dict[str, str]]]:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".csv":
        return parse_csv_bytes(data, filename)
    if suffix == ".xlsx":
        return parse_xlsx_bytes(data)
    raise InputError("Supported file types are .csv and .xlsx. Legacy .xls, PDFs, images, and macros are unsupported.")


def _safe_formula_text(value: str) -> bool:
    trimmed = value.lstrip()
    return bool(trimmed) and trimmed[0] in ("=", "+", "@")


def audit(sheets: dict[str, list[dict[str, str]]], mappings: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """Audit already-parsed records. The output is deterministic and JSON-ready."""
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
        map_for_sheet = (mappings or {}).get(sheet) or column_map(headers)
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

    description_groups: dict[str, list[tuple[str, int, dict[str, str]]]] = defaultdict(list)
    duplicate_keys: dict[tuple[str, str, str, str], list[tuple[str, int]]] = defaultdict(list)
    category_amounts: Counter[str] = Counter()
    total_amount = Decimal("0")
    for sheet, row, original, values in all_rows:
        desc = values.get("description", "").strip()
        qty = number(values.get("quantity"))
        rate = number(values.get("rate"))
        amount = number(values.get("amount"))
        unit = values.get("unit", "").strip()
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
            category = normalize_name(values.get("category"))
            if category and amount > 0:
                category_amounts[category] += amount
        for field, value in original.items():
            if field.startswith("__"):
                continue
            if _safe_formula_text(value):
                add("Low", "R013", sheet, row, field, "Text starts with a formula-like character.", value, "Preserve as text and review before spreadsheet export.")
        if desc:
            description_groups[normalize_name(desc)].append((sheet, row, values))
            duplicate_keys[(normalize_name(desc), normalize_name(unit), str(qty), str(rate))].append((sheet, row))
        markup, margin = number(values.get("markup_pct"), percent=True), number(values.get("margin_pct"), percent=True)
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
                add("Medium", "R008", sheet, row, "description", "Exact duplicate item key detected.", f"{key[0]} at {locations}", "Confirm the repeat is intended or remove the duplicate.")
    for desc, group in description_groups.items():
        signatures = {(normalize_name(v.get("unit")), str(number(v.get("quantity"))), str(number(v.get("rate")))) for _, _, v in group}
        units = {normalize_name(v.get("unit")) for _, _, v in group if v.get("unit", "").strip()}
        if len(group) > 1 and len(signatures) > 1:
            for sheet, row, _ in group:
                add("High", "R009", sheet, row, "description", "Same description has conflicting values.", desc, "Confirm the lines represent distinct scope and values.")
        if len(units) > 1:
            for sheet, row, _ in group:
                add("High", "R010", sheet, row, "unit", "Same description uses inconsistent units.", ", ".join(sorted(units)), "Confirm scope segmentation and units.")
    if total_amount > 0:
        for category, value in category_amounts.items():
            if value / total_amount > Decimal("0.80"):
                add("Medium", "R014", "Summary", 0, "category", "One category exceeds 80% of supplied amount.", f"{category}: {value / total_amount:.1%}", "Check concentration and category classification.")
    positive_rates = sorted(rate for _, _, _, values in all_rows if (rate := number(values.get("rate"))) is not None and rate > 0)
    if len(positive_rates) >= 4:
        midpoint = len(positive_rates) // 2
        median = (positive_rates[midpoint - 1] + positive_rates[midpoint]) / 2 if len(positive_rates) % 2 == 0 else positive_rates[midpoint]
        if median > 0:
            for sheet, row, _, values in all_rows:
                rate = number(values.get("rate"))
                if rate is not None and rate > 0 and (rate > median * 10 or rate < median / 10):
                    add("Medium", "R015", sheet, row, "rate", "Rate is an order-of-magnitude outlier versus this file's median positive rate.", f"rate {rate}; median {median}", "Check units, decimal placement, and source rate. This is not a correctness judgement.")

    counts = Counter(finding.severity for finding in findings)
    score = max(0, 100 - sum(SEVERITY_WEIGHT[f.severity] for f in findings))
    return {
        "findings": [finding.to_dict() for finding in findings],
        "counts": {severity: counts.get(severity, 0) for severity in ("Critical", "High", "Medium", "Low")},
        "score": score,
        "rows_reviewed": len(all_rows),
        "sheets_reviewed": sorted(sheets),
        "score_explanation": "100 minus 20 per Critical, 10 per High, 5 per Medium, and 2 per Low finding; never below 0. It measures deterministic review prompts, not bid correctness or readiness.",
    }


def findings_csv(result: dict[str, Any]) -> bytes:
    def safe_cell(value: Any) -> Any:
        text = str(value)
        # Defend recipients opening the report in a spreadsheet application.
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

    out = io.StringIO(newline="")
    fields = ["id", "severity", "rule_id", "sheet", "row", "field", "message", "evidence", "recommended_action"]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows([{field: safe_cell(finding[field]) for field in fields} for finding in result["findings"]])
    return out.getvalue().encode("utf-8")


def management_summary_html(result: dict[str, Any], filename: str) -> bytes:
    counts = result["counts"]
    rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(finding[key]))}</td>" for key in ("severity", "rule_id", "sheet", "row", "message", "evidence", "recommended_action")) + "</tr>"
        for finding in result["findings"]
    ) or "<tr><td colspan='7'>No deterministic findings.</td></tr>"
    page = f"""<!doctype html><html><head><meta charset='utf-8'><title>Bid review summary</title><style>body{{font-family:Arial,sans-serif;margin:2rem;color:#17212b}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{border:1px solid #b8c2cc;padding:6px;text-align:left}}th{{background:#e8f0f5}}.warn{{background:#fff7e1;padding:12px;border-left:4px solid #b7791f}}</style></head><body><h1>Civil Bid Readiness Auditor — Management Summary</h1><p>Input: {html.escape(filename)} | Rows reviewed: {result['rows_reviewed']} | Review-status score: <strong>{result['score']}/100</strong></p><div class='warn'><strong>Required human review:</strong> this report flags deterministic data-quality prompts only. It does not validate price, quantity, scope, profitability, contract compliance, or a bid decision.</div><h2>Finding counts</h2><p>Critical: {counts['Critical']} | High: {counts['High']} | Medium: {counts['Medium']} | Low: {counts['Low']}</p><p>{html.escape(result['score_explanation'])}</p><h2>Findings</h2><table><thead><tr><th>Severity</th><th>Rule</th><th>Sheet</th><th>Row</th><th>Finding</th><th>Evidence</th><th>Recommended action</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
    return page.encode("utf-8")
