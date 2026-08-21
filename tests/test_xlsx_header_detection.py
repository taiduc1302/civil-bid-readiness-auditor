from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from audit_engine import audit, parse_upload


def xlsx_bytes(rows: list[list[str]]) -> bytes:
    """Build a minimal single-sheet XLSX fixture using inline strings."""
    def col(index: int) -> str:
        answer = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            answer = chr(65 + remainder) + answer
        return answer

    row_xml = "".join(
        "<row r='{row}'>{cells}</row>".format(
            row=row_index,
            cells="".join(
                f"<c r='{col(cell_index)}{row_index}' t='inlineStr'><is><t>{value}</t></is></c>"
                for cell_index, value in enumerate(values)
            ),
        )
        for row_index, values in enumerate(rows, 1)
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as book:
        book.writestr(
            "[Content_Types].xml",
            "<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
            "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
            "<Default Extension='xml' ContentType='application/xml'/>"
            "<Override PartName='/xl/workbook.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'/>"
            "<Override PartName='/xl/worksheets/sheet1.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'/>"
            "</Types>",
        )
        book.writestr(
            "_rels/.rels",
            "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
            "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='xl/workbook.xml'/>"
            "</Relationships>",
        )
        book.writestr(
            "xl/workbook.xml",
            "<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' "
            "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>"
            "<sheets><sheet name='Estimate' sheetId='1' r:id='rId1'/></sheets></workbook>",
        )
        book.writestr(
            "xl/_rels/workbook.xml.rels",
            "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
            "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet' Target='worksheets/sheet1.xml'/>"
            "</Relationships>",
        )
        book.writestr(
            "xl/worksheets/sheet1.xml",
            "<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
            f"<sheetData>{row_xml}</sheetData></worksheet>",
        )
    return out.getvalue()


class XlsxHeaderDetectionTests(unittest.TestCase):
    def test_metadata_rows_before_header_are_skipped(self):
        data = xlsx_bytes([
            ["Fictional Civil Estimate"],
            ["Project", "Demo Subdivision"],
            [],
            ["Description", "Quantity", "Unit", "Rate", "Amount"],
            ["300mm Pipe", "10", "M", "100", "1000"],
        ])
        sheets = parse_upload("estimate.xlsx", data)
        self.assertEqual(sheets["Estimate"][0]["Description"], "300mm Pipe")
        self.assertEqual(sheets["Estimate"][0]["__source_row"], "5")
        self.assertEqual(audit(sheets)["score"], 100)

    def test_alias_header_after_metadata_is_detected(self):
        data = xlsx_bytes([
            ["Estimate No.", "E-100"],
            ["Prepared for review"],
            ["Scope", "Qty", "UOM", "Unit Price", "Bid Item No"],
            ["Excavation", "100", "BCY", "12.5", "100"],
        ])
        sheets = parse_upload("estimate.xlsx", data)
        result = audit(sheets)
        self.assertEqual(result["rows_reviewed"], 1)
        self.assertEqual(result["score"], 100)
        self.assertEqual(sheets["Estimate"][0]["__source_row"], "4")

    def test_first_row_fallback_is_retained_when_alias_confidence_is_low(self):
        data = xlsx_bytes([
            ["Custom Scope", "Custom Qty", "Measure", "Custom Rate"],
            ["Pipe", "2", "EA", "10"],
        ])
        sheets = parse_upload("estimate.xlsx", data)
        self.assertIn("Custom Scope", sheets["Estimate"][0])
        self.assertEqual(sheets["Estimate"][0]["__source_row"], "2")


if __name__ == "__main__":
    unittest.main()
