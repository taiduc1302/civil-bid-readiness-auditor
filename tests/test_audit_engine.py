from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from audit_engine import InputError, audit, column_map, findings_csv, management_summary_html, parse_csv_bytes, parse_upload


def xlsx_bytes(sheets: dict[str, list[list[str]]]) -> bytes:
    """Minimal OOXML fixture: inline strings, sufficient for an independent XLSX parser test."""
    def col(index: int) -> str:
        answer = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            answer = chr(65 + remainder) + answer
        return answer
    content_types = """<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/xl/workbook.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'/>{}</Types>""".format("".join(f"<Override PartName='/xl/worksheets/sheet{i}.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'/>" for i in range(1, len(sheets) + 1)))
    workbook = "".join(f"<sheet name='{name}' sheetId='{i}' r:id='rId{i}'/>" for i, name in enumerate(sheets, 1))
    rels = "".join(f"<Relationship Id='rId{i}' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet' Target='worksheets/sheet{i}.xml'/>" for i in range(1, len(sheets) + 1))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as book:
        book.writestr("[Content_Types].xml", content_types)
        book.writestr("_rels/.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='xl/workbook.xml'/></Relationships>")
        book.writestr("xl/workbook.xml", f"<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'><sheets>{workbook}</sheets></workbook>")
        book.writestr("xl/_rels/workbook.xml.rels", f"<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>{rels}</Relationships>")
        for sheet_index, rows in enumerate(sheets.values(), 1):
            row_xml = "".join("<row r='{row}'>{cells}</row>".format(row=row_index, cells="".join(f"<c r='{col(cell_index)}{row_index}' t='inlineStr'><is><t>{value}</t></is></c>" for cell_index, value in enumerate(values))) for row_index, values in enumerate(rows, 1))
            book.writestr(f"xl/worksheets/sheet{sheet_index}.xml", f"<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData>{row_xml}</sheetData></worksheet>")
    return out.getvalue()


class AuditEngineTests(unittest.TestCase):
    def sample_result(self):
        path = Path(__file__).resolve().parents[1] / "samples" / "synthetic_civil_estimate.csv"
        return audit(parse_upload(path.name, path.read_bytes()))

    def test_csv_and_alias_mapping(self):
        sheets = parse_csv_bytes(b"Item,Qty,UOM,Unit Price,Total\nPipe,2,EA,10,20\n")
        headers = list(sheets["upload"][0])
        self.assertEqual(column_map(headers), {"description": "Item", "quantity": "Qty", "unit": "UOM", "rate": "Unit Price", "amount": "Total"})
        result = audit(sheets)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["rows_reviewed"], 1)

    def test_optional_hierarchy_aliases_are_detected(self):
        headers = ["Description", "Qty", "UOM", "Unit Price", "Bid Item No", "Activity Code", "Resource Type", "Resource Code"]
        mapped = column_map(headers)
        self.assertEqual(mapped["bid_item"], "Bid Item No")
        self.assertEqual(mapped["activity"], "Activity Code")
        self.assertEqual(mapped["resource_type"], "Resource Type")
        self.assertEqual(mapped["resource_code"], "Resource Code")

    def test_blank_malformed_and_unsupported_input(self):
        with self.assertRaisesRegex(InputError, "blank"):
            parse_csv_bytes(b"")
        with self.assertRaisesRegex(InputError, "Supported file types"):
            parse_upload("estimate.xls", b"not-xls")
        with self.assertRaisesRegex(InputError, "readable XLSX"):
            parse_upload("estimate.xlsx", b"not-xlsx")

    def test_xlsx_multiple_worksheets(self):
        data = xlsx_bytes({
            "Estimate": [["Description", "Quantity", "Unit", "Rate", "Amount"], ["Pipe", "2", "EA", "10", "20"]],
            "Alternates": [["Description", "Quantity", "Unit", "Rate", "Amount"], ["Rock", "1", "LS", "50", "50"]],
        })
        sheets = parse_upload("estimate.xlsx", data)
        self.assertEqual(set(sheets), {"Estimate", "Alternates"})
        self.assertEqual(audit(sheets)["rows_reviewed"], 2)

    def test_xlsx_preserves_source_row_after_blank_rows(self):
        data = xlsx_bytes({"Estimate": [["Description", "Quantity", "Unit", "Rate"], [], ["Pipe", "", "EA", "10"]]})
        result = audit(parse_upload("estimate.xlsx", data))
        missing_qty = next(item for item in result["findings"] if item["rule_id"] == "R002")
        self.assertEqual(missing_qty["row"], 3)

    def test_missing_mapping_is_actionable(self):
        with self.assertRaisesRegex(InputError, "Required columns"):
            audit({"Rows": [{"Item": "Pipe", "Qty": "2"}]})

    def test_sample_detects_required_edge_cases_and_is_reproducible(self):
        first, second = self.sample_result(), self.sample_result()
        self.assertEqual(first["score"], second["score"])
        rule_ids = {item["rule_id"] for item in first["findings"]}
        for rule in ("R002", "R003", "R005", "R006", "R008", "R009", "R010", "R011", "R012", "R013"):
            self.assertIn(rule, rule_ids)
        self.assertLess(first["score"], 100)
        self.assertGreater(first["counts"]["High"], 0)
        self.assertEqual(first["score"], 0)
        self.assertEqual(first["counts"], {"Critical": 0, "High": 11, "Medium": 2, "Low": 1})

    def test_same_description_in_different_bid_items_is_not_conflict(self):
        result = audit({"Rows": [
            {"Description": "Excavation", "Quantity": "100", "Unit": "BCY", "Rate": "12", "Bid Item No": "100", "Activity Code": "EXC"},
            {"Description": "Excavation", "Quantity": "250", "Unit": "BCY", "Rate": "15", "Bid Item No": "200", "Activity Code": "EXC"},
        ]})
        rule_ids = {item["rule_id"] for item in result["findings"]}
        self.assertNotIn("R009", rule_ids)
        self.assertNotIn("R010", rule_ids)

    def test_same_description_in_same_context_still_conflicts(self):
        result = audit({"Rows": [
            {"Description": "Excavation", "Quantity": "100", "Unit": "BCY", "Rate": "12", "Bid Item No": "100", "Activity Code": "EXC"},
            {"Description": "Excavation", "Quantity": "250", "Unit": "BCY", "Rate": "15", "Bid Item No": "100", "Activity Code": "EXC"},
        ]})
        self.assertIn("R009", {item["rule_id"] for item in result["findings"]})

    def test_rate_outliers_are_compared_only_with_peer_unit_and_class(self):
        rows = [
            {"Description": "Excavator A", "Quantity": "1", "Unit": "HR", "Rate": "180", "Resource Type": "Equipment"},
            {"Description": "Excavator B", "Quantity": "1", "Unit": "HR", "Rate": "190", "Resource Type": "Equipment"},
            {"Description": "Dozer", "Quantity": "1", "Unit": "HR", "Rate": "200", "Resource Type": "Equipment"},
            {"Description": "Loader", "Quantity": "1", "Unit": "HR", "Rate": "2500", "Resource Type": "Equipment"},
            {"Description": "Mobilization", "Quantity": "1", "Unit": "LS", "Rate": "50000", "Resource Type": "Subcontract"},
        ]
        result = audit({"Rows": rows})
        outliers = [item for item in result["findings"] if item["rule_id"] == "R015"]
        self.assertEqual(len(outliers), 1)
        self.assertEqual(outliers[0]["row"], 5)
        self.assertIn("unit hr", outliers[0]["evidence"])
        self.assertIn("class equipment", outliers[0]["evidence"])

    def test_different_units_do_not_create_global_rate_outlier(self):
        rows = [
            {"Description": "Mobilization", "Quantity": "1", "Unit": "LS", "Rate": "50000"},
            {"Description": "Pipe", "Quantity": "1", "Unit": "M", "Rate": "120"},
            {"Description": "Gravel", "Quantity": "1", "Unit": "TON", "Rate": "40"},
            {"Description": "Labour", "Quantity": "1", "Unit": "HR", "Rate": "50"},
        ]
        result = audit({"Rows": rows})
        self.assertNotIn("R015", {item["rule_id"] for item in result["findings"]})

    def test_manual_required_mapping_keeps_auto_detected_context(self):
        sheets = {"Rows": [{"Scope": "Pipe", "Q": "2", "Measure": "EA", "Price Each": "10", "Bid Item No": "300"}]}
        mappings = {"Rows": {"description": "Scope", "quantity": "Q", "unit": "Measure", "rate": "Price Each"}}
        result = audit(sheets, mappings)
        self.assertEqual(result["rows_reviewed"], 1)
        self.assertEqual(result["score"], 100)

    def test_long_special_and_formula_like_text_is_safe(self):
        long_description = "Road <&> " + "x" * 1000
        result = audit({"Rows": [{"Description": long_description, "Quantity": "999999999", "Unit": "EA", "Rate": "0.01", "Amount": "9999999.99", "Notes": "=1+1"}]})
        self.assertIn("R013", {item["rule_id"] for item in result["findings"]})
        self.assertEqual(result["rows_reviewed"], 1)

    def test_category_concentration_and_negative_rate(self):
        result = audit({"Rows": [
            {"Description": "A", "Quantity": "1", "Unit": "EA", "Rate": "100", "Amount": "100", "Category": "Materials"},
            {"Description": "B", "Quantity": "1", "Unit": "EA", "Rate": "-1", "Amount": "-1", "Category": "Labour"},
        ]})
        rule_ids = {item["rule_id"] for item in result["findings"]}
        self.assertIn("R006", rule_ids)
        self.assertIn("R014", rule_ids)

    def test_report_exports_include_disclaimer(self):
        result = self.sample_result()
        exported = findings_csv(result).decode("utf-8")
        summary = management_summary_html(result, "synthetic.csv").decode("utf-8")
        self.assertIn("rule_id", exported)
        self.assertIn("'=SUM(A1:A2)", exported)
        self.assertIn("does not validate", summary)
        self.assertIn("synthetic.csv", summary)


if __name__ == "__main__":
    unittest.main()
