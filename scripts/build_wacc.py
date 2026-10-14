"""Restructure the WACC section of the Inputs tab: three CAPM versions + a beta dropdown.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it). Rows are
found by their label in column A. Hand-entered cells (share price, price date,
raw beta, market risk premium) are moved with their value, style and note
untouched. The Forecast section is moved down below the new block, including
its dropdown. Refuses to run if anything references the Inputs tab (moving
rows would break it), if the workbook is open in Excel, or if the WACC block
was already rebuilt.

Excel isn't available to recalculate, so the new formulas are evaluated in
Python (including WACC under each dropdown choice) and the workbook is diffed
before vs after.

Usage:
    python scripts/build_wacc.py
"""

import re
import sys
from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SHEET = "Inputs"
NCOLS = 3  # label | value | units / notes

PCT, BETA = "0.00%", "0.00"
BETA_CHOICES = ["raw", "adjusted", "industry"]
PRESERVED = ["Share price", "Price date", "Raw beta", "Market risk premium"]
OLD_WACC_ROWS = {"Risk-free rate", "Raw beta", "Adjusted beta", "Market risk premium",
                 "Cost of equity", "WACC"}

RF_NOTE = "Fed H.15, 10Y Treasury constant maturity, Oct 13 2026 (latest available)"

# New WACC block, in order: (label, kind, value or formula template, number format, note).
# kind: input / formula / keep (moved as-is from the old block). {Row label} placeholders
# in formulas are replaced by that row's value cell.
WACC_BLOCK = [
    ("Risk-free rate", "input", 0.0521, PCT, RF_NOTE),
    ("Market risk premium", "keep", None, None, None),
    ("Raw beta", "keep", None, None, None),
    ("Adjusted beta (Blume)", "formula", "=0.67*{Raw beta}+0.33", BETA,
     "Blume adjustment: pulls beta toward 1"),
    ("Industry beta", "input", 1.25, BETA,
     "Damodaran, US Software (System & Application), unlevered beta corrected for cash, Jan 2026"),
    ("Cost of equity: raw beta", "formula",
     "={Risk-free rate}+{Raw beta}*{Market risk premium}", PCT, "CAPM"),
    ("Cost of equity: adjusted beta", "formula",
     "={Risk-free rate}+{Adjusted beta (Blume)}*{Market risk premium}", PCT, "CAPM"),
    ("Cost of equity: industry beta", "formula",
     "={Risk-free rate}+{Industry beta}*{Market risk premium}", PCT, "CAPM"),
    ("Base-case beta choice", "input", "industry", "General", "Which beta drives the model"),
    ("Cost of equity (base)", "formula",
     '=CHOOSE(MATCH({Base-case beta choice},{"raw","adjusted","industry"},0),'
     "{Cost of equity: raw beta},{Cost of equity: adjusted beta},{Cost of equity: industry beta})",
     PCT, None),
    ("Debt weight", "input", 0, PCT, "No debt: convertible notes settled Nov 2025"),
    ("WACC", "formula", "={Cost of equity (base)}*(1-{Debt weight})+{Debt weight}*0", PCT,
     "≈ cost of equity, since Shopify has no debt"),
]
CHOICE_ROW = "Base-case beta choice"


def fill_refs(template, ref):
    """Replace {Row label} with that row's value cell; other braces (array constants) stay."""
    return re.sub(r"\{([^{}]+)\}", lambda m: ref.get(m.group(1), m.group(0)), template)


def find_layout(ws):
    """Header row, then {section: [(row, label), ...]} and {section: section row}."""
    header = next(r for r in range(1, ws.max_row + 1)
                  if ws.cell(r, 1).style == "Header" and ws.cell(r, 2).value == "Value")
    sections, section_rows, current = {}, {}, None
    for r in range(header + 1, ws.max_row + 1):
        label = ws.cell(r, 1).value
        if label is None:
            continue
        if ws.cell(r, 1).style == "Section":
            current = label
            sections[current], section_rows[current] = [], r
        else:
            sections[current].append((r, label))
    return header, sections, section_rows


def grab(ws, r):
    """Everything about a row's cells, so it can be written elsewhere unchanged."""
    out = []
    for c in range(1, NCOLS + 1):
        cell = ws.cell(r, c)
        out.append((cell.value, copy(cell._style),
                    (cell.comment.text, cell.comment.author) if cell.comment else None))
    return out


def put(ws, r, saved):
    for c, (value, style, comment) in enumerate(saved, start=1):
        cell = ws.cell(r, c)
        cell.value, cell._style = value, copy(style)
        cell.comment = Comment(*comment) if comment else None


def clear(ws, r):
    for c in range(1, NCOLS + 1):
        cell = ws.cell(r, c)
        cell.value, cell.comment = None, None
        cell.style = "Normal"


def snapshot(wb):
    snap = {}
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                snap[(ws.title, c.coordinate)] = (
                    c.value, c.style, c.number_format, c.font.color.rgb if c.font.color else None,
                    c.fill.fgColor.rgb, c.comment.text if c.comment else None)
        snap[(ws.title, "_validations")] = sorted(
            (str(dv.sqref), dv.formula1) for dv in ws.data_validations.dataValidation)
    return snap


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)

    refs = [f"{s.title}!{c.coordinate}" for s in wb for row in s.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=") and SHEET in c.value]
    if refs:
        sys.exit(f"Cells reference {SHEET}; moving rows would break them: {refs}")

    ws = wb[SHEET]
    _, sections, section_rows = find_layout(ws)
    wacc = dict((label, r) for r, label in sections["WACC"])
    if "Adjusted beta (Blume)" in wacc:
        sys.exit("WACC block already rebuilt; nothing to do.")
    unexpected = set(wacc) - OLD_WACC_ROWS
    if unexpected:
        sys.exit(f"Unexpected rows in the WACC section, not touching it: {sorted(unexpected)}")

    labels = {label: r for rows in sections.values() for r, label in rows}
    preserved_before = {label: grab(ws, labels[label]) for label in PRESERVED}

    # Save the Forecast section (section row + items) and the validations on it
    f_start = section_rows["Forecast"]
    f_end = max(r for r, _ in sections["Forecast"])
    forecast = [grab(ws, r) for r in range(f_start, f_end + 1)]
    forecast_dvs = [dv for dv in ws.data_validations.dataValidation
                    if any(f_start <= rng.min_row <= f_end for rng in dv.sqref.ranges)]

    kept = {label: grab(ws, wacc[label]) for label, kind, *_ in WACC_BLOCK if kind == "keep"}

    # Clear the old WACC items and the Forecast block, then write the new layout
    first = section_rows["WACC"] + 1
    for r in range(first, f_end + 1):
        clear(ws, r)

    new_rows = {label: first + i for i, (label, *_) in enumerate(WACC_BLOCK)}
    ref = {label: f"B{r}" for label, r in new_rows.items()}
    for label, kind, value, fmt, note in WACC_BLOCK:
        r = new_rows[label]
        if kind == "keep":
            put(ws, r, kept[label])
            continue
        ws.cell(r, 1, label)
        cell = ws.cell(r, 2)
        cell.value = fill_refs(value, ref) if kind == "formula" else value
        cell.style = "Formula" if kind == "formula" else "Input"
        cell.number_format = fmt
        ws.cell(r, 3, note)

    choice = DataValidation(type="list", formula1='"' + ",".join(BETA_CHOICES) + '"',
                            allow_blank=False, showErrorMessage=True,
                            errorTitle="Beta choice", error="Pick raw, adjusted or industry.")
    ws.add_data_validation(choice)
    choice.add(ref[CHOICE_ROW])

    shift = first + len(WACC_BLOCK) - f_start
    for i, saved in enumerate(forecast):
        put(ws, f_start + shift + i, saved)
    for dv in forecast_dvs:
        dv.sqref = MultiCellRange([CellRange(min_col=rng.min_col, min_row=rng.min_row + shift,
                                             max_col=rng.max_col, max_row=rng.max_row + shift)
                                   for rng in dv.sqref.ranges])

    wb.save(WORKBOOK)
    print(f"Rebuilt WACC block ({len(WACC_BLOCK)} rows); Forecast moved down {shift} rows "
          f"({f_start} -> {f_start + shift})")

    report(before, preserved_before, new_rows)


# ------------------------------------------------------------ validation

def evaluate(ws, coord, overrides, cache):
    """Evaluate the formula shapes used in this block (arithmetic, CHOOSE, MATCH)."""
    if coord in overrides:
        return overrides[coord]
    if coord in cache:
        return cache[coord]
    v = ws[coord].value
    if isinstance(v, str) and v.startswith("="):
        expr = re.sub(r"\b[A-Z]{1,3}\d+\b",
                      lambda m: repr(evaluate(ws, m.group(0), overrides, cache)), v[1:])
        expr = expr.replace("{", "[").replace("}", "]")
        v = eval(expr, {"__builtins__": {}, "CHOOSE": lambda i, *xs: xs[int(i) - 1],
                        "MATCH": lambda x, arr, _: arr.index(x) + 1})
    cache[coord] = v
    return v


def report(before, preserved_before, new_rows):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]
    _, sections, _ = find_layout(ws)
    labels = {label: r for rows in sections.values() for r, label in rows}

    print("\n== Inputs tab now (rows 12 onward)")
    for r in range(12, ws.max_row + 1):
        a, b, c = (ws.cell(r, i) for i in (1, 2, 3))
        if a.value is None:
            continue
        print(f"  r{r:<3} {a.value!s:32} {b.value!s:72.72} {b.style:8} {b.number_format:10} {c.value or ''}")
    print("  dropdowns:", [(str(dv.sqref), dv.formula1) for dv in ws.data_validations.dataValidation])

    print("\n== Hand-entered cells: value, style, format and note unchanged after the move?")
    for label in PRESERVED:
        now = grab(ws, labels[label])
        same = [(v, s, cm) for v, s, cm in now] == [(v, s, cm) for v, s, cm in preserved_before[label]]
        print(f"  {'OK  ' if same else 'DIFF'} {label:22} row {labels[label]:<3} "
              f"value={now[1][0]!r:10} note={now[2][0]!r}")

    print("\n== Evaluated (Python; Excel not available to recalculate)")
    b = {label: f"B{r}" for label, r in new_rows.items()}
    cache = {}
    adj = evaluate(ws, b["Adjusted beta (Blume)"], {}, cache)
    print(f"  Adjusted beta (Blume): {adj:.4f}  (expected ≈ 2.09)")
    for label, expected in [("Cost of equity: raw beta", 0.1606), ("Cost of equity: adjusted beta", 0.1384),
                            ("Cost of equity: industry beta", 0.1039)]:
        v = evaluate(ws, b[label], {}, cache)
        print(f"  {label:32} {v:.4%}  (expected ≈ {expected:.2%}) {'OK' if abs(v - expected) < 0.0001 else 'CHECK'}")
    current = ws[b[CHOICE_ROW]].value
    for choice in BETA_CHOICES:
        overrides = {b[CHOICE_ROW]: choice}
        base = evaluate(ws, b["Cost of equity (base)"], overrides, {})
        wacc = evaluate(ws, b["WACC"], overrides, {})
        print(f"  dropdown = {choice:9} -> cost of equity (base) {base:.4%}, WACC {wacc:.4%}"
              + ("   <- current" if choice == current else ""))

    changed_tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print(f"\n== Tabs changed: {changed_tabs}")
    if changed_tabs != [SHEET]:
        sys.exit("Something outside the Inputs tab changed")


if __name__ == "__main__":
    main()
