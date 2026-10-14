"""Fill the Ratios section of the Historicals tab with live Excel formulas.

Opens model/shopify_reverse_dcf.xlsx in place and writes only the Ratios rows.
Rows are found by their label in column A, columns by the header row. Every
ratio is a formula on the cells above it; divisions are wrapped in IFERROR.

Excel isn't available to recalculate, so the script evaluates the formula
strings it wrote (Excel semantics: blank = 0, IFERROR catches #DIV/0!),
checks published anchors, and diffs the workbook before vs after.

Usage:
    python scripts/fill_ratios.py
"""

import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SHEET = "Historicals"

PERIOD_COLS = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "H1 2025", "H1 2026", "TTM Jun-26"]
# Growth: period -> prior period. Periods without a comparable prior get "n/a".
PRIOR = {"FY2022": "FY2021", "FY2023": "FY2022", "FY2024": "FY2023", "FY2025": "FY2024",
         "H1 2026": "H1 2025"}
TTM_COL = "TTM Jun-26"
TTM_FLOW_ROWS = ["Total revenue", "Gross profit", "Operating income", "Stock-based compensation",
                 "Operating cash flow", "Capex (purchases of property & equipment)",
                 "Free cash flow", "GMV"]

PCT, USD_M = "0.0%", "#,##0"
GREY = "808080"

REV, GMV, GP, OI = "Total revenue", "GMV", "Gross profit", "Operating income"
FCF, SBC = "Free cash flow", "Stock-based compensation"
FCF_SBC = "FCF − SBC"

# Ratio row -> (kind, operands, number format)
RATIOS = {
    "Revenue growth %": ("growth", REV, PCT),
    "GMV growth %": ("growth", GMV, PCT),
    "Take rate (revenue / GMV)": ("ratio", (REV, GMV), PCT),
    "Gross margin": ("ratio", (GP, REV), PCT),
    "Operating margin": ("ratio", (OI, REV), PCT),
    "FCF margin": ("ratio", (FCF, REV), PCT),
    "SBC % of revenue": ("ratio", (SBC, REV), PCT),
    FCF_SBC: ("difference", (FCF, SBC), USD_M),
    "FCF − SBC margin": ("ratio", (FCF_SBC, REV), PCT),
}

# Published/expected figures: (ratio, period) -> value
ANCHORS = {
    ("Revenue growth %", "FY2025"): 0.301, ("Revenue growth %", "H1 2026"): 0.340,
    ("Take rate (revenue / GMV)", "FY2021"): 0.0263, ("Take rate (revenue / GMV)", "FY2025"): 0.0305,
    ("Take rate (revenue / GMV)", "H1 2026"): 0.0312, ("Take rate (revenue / GMV)", "TTM Jun-26"): 0.0307,
    ("Gross margin", "FY2025"): 0.481,
    ("FCF margin", "FY2025"): 0.174, ("FCF margin", "TTM Jun-26"): 0.177,
    ("SBC % of revenue", "FY2022"): 0.098, ("SBC % of revenue", "FY2025"): 0.039,
    (FCF_SBC, "FY2025"): 1558, (FCF_SBC, "TTM Jun-26"): 1870,
    ("FCF − SBC margin", "TTM Jun-26"): 0.141,
}


def find_layout(ws):
    header_row = next(r for r in range(1, ws.max_row + 1)
                      if ws.cell(r, 1).value == "Item" and ws.cell(r, 2).value == PERIOD_COLS[0])
    cols = {ws.cell(header_row, c).value: c for c in range(1, ws.max_column + 1)
            if ws.cell(header_row, c).value}
    rows, sections, section = {}, {}, None
    for r in range(header_row + 1, ws.max_row + 1):
        label = ws.cell(r, 1).value
        if not label:
            continue
        if ws.cell(r, 1).style == "Section":
            section = label
        else:
            rows[label], sections[label] = r, section
    return cols, rows, sections


def snapshot(wb):
    snap = {}
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                snap[(ws.title, c.coordinate)] = (
                    c.value, c.style, c.number_format, c.font.color.rgb if c.font.color else None,
                    c.alignment.horizontal, c.comment.text if c.comment else None)
    return snap


# ------------------------------------------------------------ formula evaluator

class ExcelError(Exception):
    pass


REF = re.compile(r"\b([A-Z]{1,3})(\d+)\b")
IFERROR = re.compile(r'^IFERROR\((.*),\s*""\)$')


def evaluate(ws, coord, cache):
    """Value of a cell as Excel would compute it, for the formula shapes used here."""
    if coord in cache:
        return cache[coord]
    v = ws[coord].value
    if isinstance(v, str) and v.startswith("="):
        expr = v[1:]
        m = IFERROR.match(expr)
        try:
            result = arith(ws, m.group(1) if m else expr, cache)
        except ExcelError:
            if not m:
                raise
            result = ""
    else:
        result = v
    cache[coord] = result
    return result


def arith(ws, expr, cache):
    def operand(match):
        val = evaluate(ws, match.group(0), cache)
        if val is None:
            return "0"  # blank cell counts as 0 in arithmetic
        if isinstance(val, str):
            raise ExcelError("#VALUE!")
        return repr(float(val))
    py = REF.sub(operand, expr)
    if not re.fullmatch(r"[\d.eE+\-*/() ]+", py):
        raise ValueError(f"unsupported formula: {expr}")
    try:
        return eval(py, {"__builtins__": {}})  # digits and operators only, checked above
    except ZeroDivisionError:
        raise ExcelError("#DIV/0!")


# ------------------------------------------------------------ main

def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws = wb[SHEET]
    cols, rows, sections = find_layout(ws)
    L = {p: ws.cell(1, cols[p]).column_letter for p in PERIOD_COLS}

    missing = [r for r in list(RATIOS) + TTM_FLOW_ROWS if r not in rows]
    if missing:
        sys.exit(f"Rows not found in {SHEET}: {missing}")
    if any(sections[r] != "Ratios" for r in RATIOS):
        sys.exit("A ratio label was found outside the Ratios section; refusing to write.")

    # 1. TTM column must already hold FY2025 + H1 2026 - H1 2025 for every flow row used
    added = []
    for label in TTM_FLOW_ROWS:
        r = rows[label]
        expected = f"={L['FY2025']}{r}+{L['H1 2026']}{r}-{L['H1 2025']}{r}"
        cell = ws.cell(r, cols[TTM_COL])
        if cell.value != expected:
            if cell.value is not None:
                sys.exit(f"TTM {label} has {cell.value!r}, expected {expected}; not overwriting.")
            fmt = cell.number_format
            cell.value, cell.style, cell.number_format = expected, "Formula", fmt
            added.append(label)
    print("TTM formulas: all present" if not added else f"TTM formulas added for: {added}")

    # 2. Ratio formulas
    targets = set()
    for label, (kind, operand, fmt) in RATIOS.items():
        r = rows[label]
        for p in PERIOD_COLS:
            cell = ws.cell(r, cols[p])
            targets.add((SHEET, cell.coordinate))
            cell.style = "Formula"
            cell.number_format = fmt
            cell.comment = None
            if kind == "growth":
                if p not in PRIOR:
                    cell.value = "n/a"
                    cell.font = Font(color=GREY)
                    cell.alignment = Alignment(horizontal="right")
                    continue
                src = rows[operand]
                cell.value = f'=IFERROR({L[p]}{src}/{L[PRIOR[p]]}{src}-1,"")'
            elif kind == "ratio":
                num, den = rows[operand[0]], rows[operand[1]]
                cell.value = f'=IFERROR({L[p]}{num}/{L[p]}{den},"")'
            else:
                a, b = rows[operand[0]], rows[operand[1]]
                cell.value = f"={L[p]}{a}-{L[p]}{b}"

    wb.save(WORKBOOK)
    print(f"Wrote {len(targets)} Ratios cells to {WORKBOOK.relative_to(ROOT)} [{SHEET}]")

    report(targets, before, added, rows, cols)


def report(targets, before, added, rows, cols):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]
    cache = {}

    def value(label, p):
        return evaluate(ws, ws.cell(rows[label], cols[p]).coordinate, cache)

    print("\n== Ratios, evaluated from the workbook's formulas")
    print(f"  {'':28}" + "".join(f"{p:>12}" for p in PERIOD_COLS))
    for label, (_, _, fmt) in RATIOS.items():
        cells = []
        for p in PERIOD_COLS:
            v = value(label, p)
            if isinstance(v, str):
                cells.append(f"{v or '(blank)':>12}")
            elif fmt == PCT:
                cells.append(f"{v:>12.2%}")
            else:
                cells.append(f"{v:>12,.0f}")
        print(f"  {label:28}" + "".join(cells))

    print("\n== Anchors (tolerance 0.1 percentage point; FCF - SBC within 0.5)")
    ok = True
    for (label, p), expected in ANCHORS.items():
        got = value(label, p)
        tol = 0.5 if label == FCF_SBC else 0.001
        good = isinstance(got, float) and abs(got - expected) <= tol
        ok &= good
        show = (lambda x: f"{x:,.1f}") if label == FCF_SBC else (lambda x: f"{x:.2%}")
        print(f"  {'OK  ' if good else 'FAIL'} {label} {p}: {show(got) if isinstance(got, float) else got!r}"
              f" vs {show(expected)}")

    print("\n== Formulas written (FY2025 and TTM columns)")
    for label in RATIOS:
        r = rows[label]
        print(f"  {label:28} {ws.cell(r, cols['FY2025']).value!s:30} {ws.cell(r, cols['TTM Jun-26']).value}")

    allowed = targets | {(SHEET, ws.cell(rows[l], cols[TTM_COL]).coordinate) for l in added}
    others = sorted(k for k in before.keys() | after.keys() if k not in allowed and before.get(k) != after.get(k))
    print(f"\n== Cells changed outside the Ratios rows (all tabs; values, formulas, styles, comments): "
          f"{len(others)}")
    for k in others:
        print(f"  {k}: {before.get(k)} -> {after.get(k)}")

    if not ok or others:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
