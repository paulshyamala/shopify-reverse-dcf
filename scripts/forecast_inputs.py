"""Finish the Forecast section of the Inputs tab: TTM starting point and forecast settings.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it). Writes, in order:
starting revenue, TTM FCF, TTM SBC (links to Historicals), TTM after-tax interest
(formula pointing at the equity-bridge cell), the starting operating FCF margin (formula,
honours the SBC flag), forecast years, and the two terminal inputs (left blank,
ToFill). The existing SBC rows keep their order below; their formulas and the
SBC-treatment dropdown are remapped to the rows they move to.

Refuses to run if the workbook is open in Excel, if another tab references
Inputs, or if a row it replaces already holds a value. Formulas are evaluated
in Python before and after, and the workbook is diffed.

Usage:
    python scripts/forecast_inputs.py
"""

import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

from build_bridge import evaluate, remap
from build_wacc import clear, fill_refs, find_layout, grab, put, snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SHEET, HIST = "Inputs", "Historicals"
USD_M, PCT = "#,##0", "0.0%"

SECTION = "Forecast"
REPLACED = {"Starting revenue (TTM)", "Terminal FCF margin", "Terminal growth rate", "Forecast years"}
KEPT = ["SBC treatment", "SBC % of revenue (forecast)", "SBC deduction flag"]
INTEREST_ROW = "TTM interest income (after tax)"
CHECK_ROWS = ["WACC", "SBC deduction flag", INTEREST_ROW, "Net non-operating assets", "Market cap"]


def layout(hist):
    """(label, style, value or formula, format, note). {Row label} = that row's cell on Inputs."""
    return [
        ("Starting revenue (TTM)", "Link", hist("Total revenue"), USD_M, "TTM to Jun 30 2026"),
        ("TTM FCF", "Link", hist("Free cash flow"), USD_M, None),
        ("TTM SBC", "Link", hist("Stock-based compensation"), USD_M, None),
        ("TTM after-tax interest income", "Formula", "={" + INTEREST_ROW + "}", USD_M,
         "Stripped out: cash is added in the equity bridge"),
        ("Starting operating FCF margin", "Formula",
         "=IFERROR(({TTM FCF}-{SBC deduction flag}*{TTM SBC}-{TTM after-tax interest income})"
         "/{Starting revenue (TTM)},\"\")", PCT,
         "Base ≈ 12.4%. Reported FCF margin 17.7% → minus SBC → minus interest"),
        ("Forecast years", "Input", 10, "0", None),
        ("Terminal FCF margin", "ToFill", None, PCT, "Decide Thursday"),
        ("Terminal growth rate", "ToFill", None, PCT, "Decide Thursday"),
    ]


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    refs = [f"{s.title}!{c.coordinate}" for s in wb if s.title != SHEET for row in s.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=") and f"{SHEET}!" in c.value]
    if refs:
        sys.exit(f"Cells on other tabs reference {SHEET}; moving rows would break them: {refs}")

    ws, hs = wb[SHEET], wb[HIST]
    _, sections, section_rows = find_layout(ws)
    old = {label: r for r, label in sections[SECTION]}
    if "Starting operating FCF margin" in old:
        sys.exit("Forecast section already finished; nothing to do.")
    if set(old) != REPLACED | set(KEPT):
        sys.exit(f"Unexpected rows in {SECTION}: {sorted(old)}")
    filled = [label for label in REPLACED if ws.cell(old[label], 2).value is not None]
    if filled:
        sys.exit(f"Rows that would be replaced already hold values: {filled}")
    labels = {label: r for rows in sections.values() for r, label in rows}
    if INTEREST_ROW not in labels:
        sys.exit(f"{INTEREST_ROW!r} not found on {SHEET}")

    h_header = next(r for r in range(1, hs.max_row + 1) if hs.cell(r, 1).value == "Item")
    h_cols = {hs.cell(h_header, c).value: c for c in range(1, hs.max_column + 1)}
    h_rows = {hs.cell(r, 1).value: r for r in range(h_header + 1, hs.max_row + 1) if hs.cell(r, 1).value}
    hist = lambda label: f"={HIST}!{hs.cell(h_rows[label], h_cols['TTM Jun-26']).coordinate}"
    spec = layout(hist)

    old_values = {label: evaluate(wb, SHEET, f"B{labels[label]}") for label in CHECK_ROWS}
    kept = {label: grab(ws, old[label]) for label in KEPT}
    first, last = section_rows[SECTION] + 1, max(old.values())
    dvs = [dv for dv in ws.data_validations.dataValidation
           if any(first <= rng.min_row <= last for rng in dv.sqref.ranges)]

    new_rows = {label: first + i for i, (label, *_) in enumerate(spec)}
    new_rows.update({label: first + len(spec) + i for i, label in enumerate(KEPT)})
    row_map = {r: r for r in range(1, first)}  # rows above the section don't move
    row_map.update({old[label]: new_rows[label] for label in KEPT})
    ref = {label: f"B{r}" for label, r in {**labels, **new_rows}.items()}

    for r in range(first, max(last, max(new_rows.values())) + 1):
        clear(ws, r)
    for label, style, value, fmt, note in spec:
        r = new_rows[label]
        ws.cell(r, 1, label)
        cell = ws.cell(r, 2)
        cell.value = fill_refs(value, ref) if isinstance(value, str) else value
        cell.style = style
        cell.number_format = fmt
        ws.cell(r, 3, note)
    for label in KEPT:
        moved = [(remap(v, row_map) if isinstance(v, str) and v.startswith("=") else v, s, c)
                 for v, s, c in kept[label]]
        put(ws, new_rows[label], moved)
    for dv in dvs:
        dv.sqref = MultiCellRange([CellRange(min_col=rng.min_col, min_row=row_map[rng.min_row],
                                             max_col=rng.max_col, max_row=row_map[rng.max_row])
                                   for rng in dv.sqref.ranges])

    wb.save(WORKBOOK)
    print(f"{SECTION}: {len(spec)} rows written, SBC rows moved "
          f"{old[KEPT[0]]}-{old[KEPT[-1]]} -> {new_rows[KEPT[0]]}-{new_rows[KEPT[-1]]}")
    report(before, old_values, kept, new_rows)


def report(before, old_values, kept, new_rows):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]
    labels = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value}
    b = lambda label: f"B{labels[label]}"
    ok = True

    print(f"\n== {SECTION} section, evaluated")
    for label, r in new_rows.items():
        cell = ws.cell(r, 2)
        v = evaluate(wb, SHEET, cell.coordinate)
        shown = "(blank)" if v is None else f"{v:.2%}" if cell.number_format == PCT else \
            f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)
        print(f"  B{r:<3} {label:32} {shown:>10}  {cell.style:7} {cell.number_format:6} {cell.value}")

    margin, flag, treat = b("Starting operating FCF margin"), b("SBC deduction flag"), b("SBC treatment")
    print("\n== Starting operating FCF margin by SBC treatment")
    for choice, expected in [("subtract", 0.124), ("ignore", 0.160)]:
        f = evaluate(wb, SHEET, flag, {(SHEET, treat): choice})
        m = evaluate(wb, SHEET, margin, {(SHEET, treat): choice})
        good = abs(m - expected) < 0.0005
        ok &= good
        print(f"  {choice:8} -> flag {f}, margin {m:.2%} (expected ≈ {expected:.1%}) {'OK' if good else 'CHECK'}")

    print("\n== Unchanged results elsewhere on Inputs")
    for label, old_v in old_values.items():
        new_v = evaluate(wb, SHEET, b(label))
        same = old_v == new_v
        ok &= same
        print(f"  {'OK  ' if same else 'DIFF'} {label:32} {new_v}")
    for c in ("raw", "adjusted", "industry"):
        print(f"  beta choice {c:9} -> WACC {evaluate(wb, SHEET, b('WACC'), {(SHEET, b('Base-case beta choice')): c}):.4%}")
    print("  dropdowns:", [(str(dv.sqref), dv.formula1, ws[str(dv.sqref)].offset(0, -1).value)
                           for dv in ws.data_validations.dataValidation])
    for label in kept:
        plain = lambda v: None if isinstance(v, str) and v.startswith("=") else v  # formulas were remapped
        same = ([(plain(v), s, c) for v, s, c in grab(ws, labels[label])]
                == [(plain(v), s, c) for v, s, c in kept[label]])
        ok &= same
        print(f"  {'OK  ' if same else 'DIFF'} moved {label}: {ws.cell(labels[label], 2).value} "
              f"(value/style/note kept)")

    tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print(f"\n== Tabs changed: {tabs}")
    if tabs != [SHEET] or not ok:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
