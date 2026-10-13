"""Finish the Historicals tab: GMV from filings, H1 2026 debt = 0, MRR unused.

Opens model/shopify_reverse_dcf.xlsx in place and writes only the target
cells below; everything else is snapshotted before and diffed after to prove
nothing else changed. Safe to re-run.

- Convertible notes / debt, H1 2026: 0 (Input) with the settlement comment.
- MRR: not used in the model. The row stays (so references don't shift), its
  input cells are greyed out, its TTM formula removed, and it is noted.
- GMV: values from data/gmv.csv (scripts/pull_gmv.py), Input style, with a
  verbatim source comment. A missing value is left blank and ToFill.

Usage:
    python scripts/finish_historicals.py
"""

import csv
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
GMV_CSV = ROOT / "data" / "gmv.csv"
SHEET = "Historicals"

PERIOD_COLS = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "H1 2025", "H1 2026"]
TTM_COL = "TTM Jun-26"
NOTES_COL = "Source / notes"

DEBT_ROW = "Convertible notes / debt"
DEBT_PERIOD = "H1 2026"
DEBT_COMMENT = ("0 — 0.125% convertible notes settled in cash Nov 3, 2025 (FY2025 10-K cash flow "
                "statement, 'Maturities of convertible senior notes'). No debt fact in Jun-2026 10-Q.")
MRR_ROW = "MRR"
MRR_NOTE = "Not used in model"
GREY = "808080"
GMV_ROW = "GMV"
AUTHOR = "finish_historicals.py"


def find_layout(ws):
    header_row = next(r for r in range(1, ws.max_row + 1)
                      if ws.cell(r, 1).value == "Item" and ws.cell(r, 2).value == PERIOD_COLS[0])
    cols = {ws.cell(header_row, c).value: c for c in range(1, ws.max_column + 1)
            if ws.cell(header_row, c).value}
    rows = {ws.cell(r, 1).value: r for r in range(header_row + 1, ws.max_row + 1)
            if ws.cell(r, 1).value}
    return cols, rows


def snapshot(wb):
    """Everything visible about every cell, keyed by (sheet, coordinate)."""
    snap = {}
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                snap[(ws.title, c.coordinate)] = (
                    c.value, c.style, c.number_format, c.font.color.rgb if c.font.color else None,
                    c.fill.fgColor.rgb, c.comment.text if c.comment else None)
    return snap


def set_style(cell, style):
    fmt = cell.number_format
    cell.style = style
    cell.number_format = fmt


def comment(text, height=160):
    c = Comment(text, AUTHOR)
    c.width, c.height = 360, height
    return c


def gmv_comment(g):
    return (f"Source: {g['form']}, accession {g['accession_number']}\n"
            f"{g['exhibit_or_item']} > \"{g['section']}\"\n"
            f"\"{g['intro_sentence']}\"\n"
            f"Table row {g['units']}: \"{g['table_row']}\"\n"
            f"Column used: {g['column']}")


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} looks open in Excel ({lock.name} exists). Close it first.")

    with GMV_CSV.open() as fh:
        gmv = {g["period"]: g for g in csv.DictReader(fh)}

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws = wb[SHEET]
    cols, rows = find_layout(ws)
    targets = set()

    def target(r, c):
        cell = ws.cell(r, c)
        targets.add((SHEET, cell.coordinate))
        return cell

    # 1. Debt, H1 2026
    cell = target(rows[DEBT_ROW], cols[DEBT_PERIOD])
    cell.value = 0
    set_style(cell, "Input")
    cell.comment = comment(DEBT_COMMENT, 110)

    # 2. MRR: grey, unused, no TTM formula
    for p in PERIOD_COLS:
        cell = target(rows[MRR_ROW], cols[p])
        set_style(cell, "Normal")
        cell.font = Font(color=GREY)
    ttm = target(rows[MRR_ROW], cols[TTM_COL])
    ttm.value = None
    set_style(ttm, "Normal")
    target(rows[MRR_ROW], cols[NOTES_COL]).value = MRR_NOTE

    # 3. GMV
    blanks = []
    for p in PERIOD_COLS:
        cell = target(rows[GMV_ROW], cols[p])
        g = gmv.get(p)
        if g and g["value_usd_m"]:
            cell.value = float(g["value_usd_m"])
            set_style(cell, "Input")
            cell.comment = comment(gmv_comment(g))
        else:
            cell.value = None
            set_style(cell, "ToFill")
            blanks.append(p)

    wb.save(WORKBOOK)

    # Report
    after_wb = load_workbook(WORKBOOK)
    after = snapshot(after_wb)
    ws = after_wb[SHEET]

    print("== GMV (USD m)")
    for p in PERIOD_COLS:
        cell = ws.cell(rows[GMV_ROW], cols[p])
        if cell.value is None:
            print(f"  {p:8} {'BLANK':>12}  not found unambiguously in the filing")
            continue
        g = gmv[p]
        print(f"  {p:8} {cell.value:>12,.3f}  {g['form']} {g['accession_number']}, {g['column']}: "
              f"\"{g['table_row']}\" {g['units']}")
    if blanks:
        print(f"  Left blank: {', '.join(blanks)}")

    print("\n== Target cells changed")
    for key in sorted(targets, key=lambda k: (int(''.join(filter(str.isdigit, k[1]))), k[1])):
        if before.get(key) != after.get(key):
            b, a = before.get(key), after.get(key)
            print(f"  {key[1]:5} {str(b[0] if b else None):>14} -> {str(a[0]):<14} style {b[1] if b else None} -> {a[1]}")

    others = [k for k in before.keys() | after.keys() if k not in targets and before.get(k) != after.get(k)]
    print(f"\n== Other cells changed (all tabs, values/styles/formats/comments): {len(others)}")
    for k in sorted(others):
        print(f"  {k}: {before.get(k)} -> {after.get(k)}")

    yellow = [c.coordinate for row in ws.iter_rows() for c in row if c.style == "ToFill"]
    print(f"\n== Cells still yellow (ToFill) on {SHEET}: {', '.join(yellow) if yellow else 'none'}")


if __name__ == "__main__":
    main()
