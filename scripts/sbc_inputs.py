"""Step 4: SBC treatment inputs on the Inputs tab (Forecast section).

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it):
- the existing "SBC treatment" dropdown is set to "subtract" (blue Input),
- two rows are added directly below it: the forecast SBC % of revenue (input)
  and an SBC deduction flag (formula: 1 = subtract, 0 = ignore).
Refuses to run if the workbook is open in Excel, if anything references the
Inputs tab, or if the rows below "SBC treatment" are not empty.

Excel isn't available to recalculate, so the flag is evaluated in Python
under both dropdown values, and the workbook is diffed before vs after.

Usage:
    python scripts/sbc_inputs.py
"""

import re
import sys
from pathlib import Path

from openpyxl import load_workbook

from build_wacc import snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SHEET = "Inputs"

TREATMENT = "SBC treatment"
TREATMENT_VALUE = "subtract"
TREATMENT_NOTE = "Base case: SBC treated as a real cost (paid in dilution). See memo/decisions.md"

# Rows added directly below "SBC treatment": (label, style, value or formula, format, note)
NEW_ROWS = [
    ("SBC % of revenue (forecast)", "Input", 0.04, "0.0%",
     "Held flat. History: FY24 4.8%, FY25 3.9%, TTM 3.6% (Historicals)"),
    ("SBC deduction flag", "Formula", '=IF({treatment}="subtract",1,0)', "0",
     "1 = subtract SBC from FCF in DCF; 0 = ignore"),
]


def set_style(cell, style):
    fmt = cell.number_format
    cell.style = style
    cell.number_format = fmt


def evaluate(ws, coord, overrides):
    """Evaluate arithmetic, = / <> comparisons and IF, as Excel would.

    Text compares case-insensitively, like Excel.
    """
    value = overrides.get(coord, ws[coord].value)
    if not (isinstance(value, str) and value.startswith("=")):
        return value.lower() if isinstance(value, str) else value

    def ref(m):
        return repr(evaluate(ws, m.group(0), overrides))

    expr = re.sub(r'"[^"]*"', lambda m: m.group(0).lower(), value[1:])
    expr = re.sub(r"\b[A-Z]{1,3}\d+\b", ref, expr)
    expr = expr.replace("<>", "!=")
    expr = re.sub(r"(?<![<>!=])=(?!=)", "==", expr)
    return eval(expr, {"__builtins__": {}, "IF": lambda c, a, b: a if c else b})


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)

    refs = [f"{s.title}!{c.coordinate}" for s in wb for row in s.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=") and SHEET in c.value]
    if refs:
        sys.exit(f"Cells reference {SHEET}; adding rows could break them: {refs}")

    ws = wb[SHEET]
    rows = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value}
    if NEW_ROWS[0][0] in rows:
        sys.exit("SBC rows already added; nothing to do.")
    t = rows[TREATMENT]
    for r in range(t + 1, t + 1 + len(NEW_ROWS)):
        if any(ws.cell(r, c).value is not None for c in (1, 2, 3)):
            sys.exit(f"Row {r} below {TREATMENT!r} is not empty; not overwriting it.")

    targets = {(SHEET, f"{col}{r}") for r in range(t, t + 1 + len(NEW_ROWS)) for col in "ABC"}

    treatment = ws.cell(t, 2)
    treatment.value = TREATMENT_VALUE
    set_style(treatment, "Input")
    ws.cell(t, 3).value = TREATMENT_NOTE

    for i, (label, style, value, fmt, note) in enumerate(NEW_ROWS, start=1):
        r = t + i
        ws.cell(r, 1, label)
        cell = ws.cell(r, 2)
        cell.value = value.format(treatment=treatment.coordinate) if style == "Formula" else value
        cell.style = style
        cell.number_format = fmt
        ws.cell(r, 3, note)

    wb.save(WORKBOOK)
    report(before, targets, t)


def report(before, targets, t):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]

    print("== Inputs, Forecast section")
    r = t
    while ws.cell(r - 1, 1).style != "Section":
        r -= 1
    for r in range(r - 1, t + 1 + len(NEW_ROWS)):
        a, b, c = (ws.cell(r, i) for i in (1, 2, 3))
        print(f"  r{r:<3} {a.value!s:28} {b.value!s:22} {b.style:8} {b.number_format:8} | {c.value or ''}")
    print("  dropdowns:", [(str(dv.sqref), dv.formula1) for dv in ws.data_validations.dataValidation])

    print("\n== SBC deduction flag, evaluated in Python")
    flag = ws.cell(t + 2, 2).coordinate
    treatment = ws.cell(t, 2).coordinate
    ok = True
    for choice, expected in [("subtract", 1), ("ignore", 0)]:
        got = evaluate(ws, flag, {treatment: choice})
        ok &= got == expected
        print(f"  {TREATMENT} = {choice:8} -> flag {got}  (expected {expected}) {'OK' if got == expected else 'FAIL'}")
    print(f"  as saved ({ws[treatment].value!r}) -> flag {evaluate(ws, flag, {})}")

    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    outside = [k for k in changed if k not in targets]
    print(f"\n== Cells changed: {[k[1] for k in changed]}")
    print(f"   outside Inputs rows {t}-{t + len(NEW_ROWS)} (all tabs, incl. dropdowns): {outside or 'none'}")
    if outside or not ok:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
