"""Build the empty Excel skeleton for the Shopify reverse DCF.

Structure and formatting only: tabs, named cell styles, labels, number
formats. No data and no formulas.

Usage:
    python scripts/build_skeleton.py           # refuses if the workbook exists
    python scripts/build_skeleton.py --force   # overwrite an existing workbook
"""

import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, NamedStyle, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

OUTPUT = Path(__file__).resolve().parent.parent / "model" / "shopify_reverse_dcf.xlsx"

COL_A_WIDTH = 38
COL_WIDTH = 13
NOTES_WIDTH = 45
HEADER_ROW = 4  # rows 1-2: title + description, row 3: spacer

FMT_USD_M = "#,##0"
FMT_PCT = "0.0%"
FMT_PRICE = "#,##0.00"
FMT_BETA = "0.00"
FMT_DATE = "yyyy-mm-dd"
FMT_INT = "0"

DESCRIPTIONS = {
    "Inputs": "All assumptions live here. Change blue cells only.",
    "Historicals": "FY2021–FY2025 and H1 2025/H1 2026 from SEC filings. "
                   "Every hardcoded number has a source comment.",
    "DCF": "10-year forecast → FCF → discounting → terminal value → value per share.",
    "Reverse": "Solve for the revenue growth rate that makes value per share = current price.",
    "Sensitivity": "Implied growth across WACC × terminal margin and terminal growth × SBC treatment.",
    "Reality Check": "Implied 2035 revenue → GMV → share of global e-commerce vs today.",
    "Scenarios": "Bull / base / bear inputs and resulting value per share.",
}


def solid(hex_colour):
    return PatternFill(fill_type="solid", start_color=hex_colour, end_color=hex_colour)


def make_named_styles():
    return [
        NamedStyle(name="Input", font=Font(color="0000FF")),
        NamedStyle(name="Formula", font=Font(color="000000")),
        NamedStyle(name="Link", font=Font(color="008000")),
        NamedStyle(name="ToFill", font=Font(color="0000FF"), fill=solid("FFF2CC")),
        NamedStyle(name="Header", font=Font(bold=True, color="FFFFFF"), fill=solid("1F3864")),
        NamedStyle(name="Section", font=Font(bold=True), fill=solid("D9D9D9")),
    ]


def setup_sheet(ws, title, n_cols, freeze_row=None, notes_col=None):
    """Title, description, gridlines, column widths and freeze panes."""
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = DESCRIPTIONS[title]
    ws["A2"].font = Font(italic=True, color="808080")

    ws.sheet_view.showGridLines = False
    ws.sheet_format.defaultColWidth = COL_WIDTH
    ws.column_dimensions["A"].width = COL_A_WIDTH
    for col in range(2, n_cols + 1):
        ws.column_dimensions[get_column_letter(col)].width = COL_WIDTH
    if notes_col:
        ws.column_dimensions[get_column_letter(notes_col)].width = NOTES_WIDTH

    if freeze_row:
        ws.freeze_panes = f"A{freeze_row}"


def header_row(ws, row, labels, n_cols=None):
    n_cols = n_cols or len(labels)
    for col in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.style = "Header"
        if col <= len(labels):
            cell.value = labels[col - 1]


def section_row(ws, row, label, n_cols):
    for col in range(1, n_cols + 1):
        ws.cell(row=row, column=col).style = "Section"
    ws.cell(row=row, column=1).value = label


def build_inputs(ws):
    n_cols = 3

    # Colour legend: one sample cell per named style
    legend = [
        ("Input", 1234, "Hardcoded numbers and assumptions"),
        ("Formula", 1234, "Calculations"),
        ("Link", 1234, "References to another tab"),
        ("ToFill", None, "Input cells still to be filled"),
        ("Header", "Header", "Column headers"),
        ("Section", "Section", "Section separators"),
    ]
    row = HEADER_ROW
    section_row(ws, row, "Colour legend", n_cols)
    for name, sample, meaning in legend:
        row += 1
        ws.cell(row=row, column=1, value=name)
        sample_cell = ws.cell(row=row, column=2, value=sample)
        sample_cell.style = name
        if isinstance(sample, int):
            sample_cell.number_format = FMT_USD_M
        ws.cell(row=row, column=3, value=meaning)

    # Input table
    row += 2
    header_row(ws, row, ["Input", "Value", "Units / notes"])

    groups = [
        ("Market", [
            ("Share price", "USD/share", FMT_PRICE),
            ("Diluted shares outstanding", "m shares", FMT_USD_M),
            ("Price date", "date", FMT_DATE),
        ]),
        ("Balance sheet", [
            ("Cash & equivalents", "USD m", FMT_USD_M),
            ("Marketable securities", "USD m", FMT_USD_M),
            ("Equity investments", "USD m", FMT_USD_M),
            ("Debt", "USD m", FMT_USD_M),
        ]),
        ("WACC", [
            ("Risk-free rate", "%", FMT_PCT),
            ("Raw beta", "x", FMT_BETA),
            ("Adjusted beta", "x", FMT_BETA),
            ("Market risk premium", "%", FMT_PCT),
            ("Cost of equity", "%", FMT_PCT),
            ("WACC", "%", FMT_PCT),
        ]),
        ("Forecast", [
            ("Starting revenue (TTM)", "USD m", FMT_USD_M),
            ("Terminal FCF margin", "%", FMT_PCT),
            ("Terminal growth rate", "%", FMT_PCT),
            ("Forecast years", "years (10)", FMT_INT),
            ("SBC treatment", "subtract / ignore", None),
        ]),
    ]

    for group, items in groups:
        row += 1
        section_row(ws, row, group, n_cols)
        for label, units, fmt in items:
            row += 1
            ws.cell(row=row, column=1, value=label)
            value_cell = ws.cell(row=row, column=2)
            value_cell.style = "ToFill"
            if fmt:
                value_cell.number_format = fmt
            ws.cell(row=row, column=3, value=units)
            if label == "SBC treatment":
                dv = DataValidation(type="list", formula1='"subtract,ignore"', allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(value_cell)

    # No freeze panes here: the legend above the table would eat the screen
    setup_sheet(ws, "Inputs", n_cols, notes_col=3)


def build_historicals(ws):
    columns = ["Item", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025",
               "H1 2025", "H1 2026", "TTM Jun-26", "Source / notes"]
    n_cols = len(columns)
    first_period_col, ttm_col = 2, 9

    header_row(ws, HEADER_ROW, columns)

    # (label, is_ratio, is_derived): derived rows are calculations, styled Formula
    groups = [
        ("Income statement", [
            ("Total revenue", False, False),
            ("Subscription solutions revenue", False, False),
            ("Merchant solutions revenue", False, False),
            ("Gross profit", False, False),
            ("Operating income", False, False),
            ("Stock-based compensation", False, False),
        ]),
        ("Cash flow", [
            ("Operating cash flow", False, False),
            ("Capex (purchases of property & equipment)", False, False),
            ("Free cash flow", False, True),
        ]),
        ("Balance sheet", [
            ("Cash & equivalents", False, False),
            ("Marketable securities", False, False),
            ("Equity & other investments", False, False),
            ("Convertible notes / debt", False, False),
        ]),
        ("Shares", [
            ("Diluted weighted-average shares", False, False),
            ("Shares outstanding (cover page)", False, False),
        ]),
        ("KPIs", [
            ("GMV", False, False),
            ("MRR", False, False),
        ]),
        ("Ratios", [
            ("Revenue growth %", True, True),
            ("GMV growth %", True, True),
            ("Take rate (revenue / GMV)", True, True),
            ("Gross margin", True, True),
            ("Operating margin", True, True),
            ("FCF margin", True, True),
            ("SBC % of revenue", True, True),
            ("FCF − SBC", False, True),
            ("FCF − SBC margin", True, True),
        ]),
    ]

    row = HEADER_ROW
    for group, items in groups:
        row += 1
        section_row(ws, row, group, n_cols)
        for label, is_ratio, is_derived in items:
            row += 1
            ws.cell(row=row, column=1, value=label)
            for col in range(first_period_col, ttm_col + 1):
                cell = ws.cell(row=row, column=col)
                # TTM is always computed from FY2025 + H1 2026 − H1 2025
                cell.style = "Formula" if is_derived or col == ttm_col else "Input"
                cell.number_format = FMT_PCT if is_ratio else FMT_USD_M

    setup_sheet(ws, "Historicals", n_cols, HEADER_ROW + 1, notes_col=n_cols)


def build_placeholder(ws, title):
    """Tabs with no layout yet: title, description and an empty header band."""
    n_cols = 12  # label column + base year + 10 forecast years
    header_row(ws, HEADER_ROW, ["Item"], n_cols)
    setup_sheet(ws, title, n_cols, HEADER_ROW + 1)


def build_workbook():
    wb = Workbook()
    for style in make_named_styles():
        wb.add_named_style(style)

    builders = {"Inputs": build_inputs, "Historicals": build_historicals}
    wb.remove(wb.active)
    for title in DESCRIPTIONS:
        ws = wb.create_sheet(title)
        if title in builders:
            builders[title](ws)
        else:
            build_placeholder(ws, title)

    wb.active = 0
    return wb


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true",
                        help="overwrite the workbook if it already exists")
    args = parser.parse_args()

    if OUTPUT.exists() and not args.force:
        sys.exit(f"Refusing to overwrite {OUTPUT} (it may contain manual edits). "
                 "Re-run with --force to replace it.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    build_workbook().save(OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
