"""Tidy the Inputs tab after the WACC rebuild.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it):
- filled-in input cells get the blue Input style (number formats kept),
- market risk premium shown as 0.00%,
- price date converted from text to a real Excel date,
- WACC note points to memo/decisions.md.
Then evaluates WACC and diffs the workbook to prove nothing else changed.

Usage:
    python scripts/tidy_inputs.py
"""

import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import load_workbook

from build_wacc import evaluate, snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SHEET = "Inputs"

FILLED_INPUTS = ["Share price", "Price date", "Risk-free rate", "Market risk premium", "Raw beta",
                 "Industry beta", "Debt weight", "Base-case beta choice"]
FORMATS = {"Market risk premium": "0.00%", "Price date": "yyyy-mm-dd"}
PRICE_DATE = date(2026, 10, 14)
WACC_NOTE = ("Base case: CAPM with Damodaran software industry beta (1.25). "
             "See memo/decisions.md")
EXPECTED_CHOICE, EXPECTED_WACC = "industry", 0.1039


def excel_display(x, places):
    """Round like Excel's display: 15 significant digits first, then half-up."""
    return float(Decimal(f"{x:.15g}").quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP))


def set_style(cell, style):
    fmt = cell.number_format
    cell.style = style
    cell.number_format = fmt


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws = wb[SHEET]
    rows = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value}
    missing = [label for label in FILLED_INPUTS + ["WACC", "Cost of equity (base)"] if label not in rows]
    if missing:
        sys.exit(f"Rows not found on {SHEET}: {missing}")

    targets = set()

    def cell(label, col=2):
        c = ws.cell(rows[label], col)
        targets.add((SHEET, c.coordinate))
        return c

    # Price date: text -> real date, only if the text is the date we expect
    pd = cell("Price date")
    if isinstance(pd.value, str):
        parsed = datetime.strptime(pd.value.strip(), "%b %d %Y").date()
        if parsed != PRICE_DATE:
            sys.exit(f"Price date text {pd.value!r} is not {PRICE_DATE}; not converting.")
        pd.value = PRICE_DATE

    for label in FILLED_INPUTS:
        c = cell(label)
        if c.value is None:
            sys.exit(f"{label} is empty; it should be filled before switching to Input.")
        set_style(c, "Input")
    for label, fmt in FORMATS.items():
        cell(label).number_format = fmt

    cell("WACC", col=3).value = WACC_NOTE

    wb.save(WORKBOOK)
    report(before, targets, rows)


def report(before, targets, rows):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]

    print("== Inputs cells after tidy-up")
    for label in FILLED_INPUTS + ["WACC"]:
        b, c = ws.cell(rows[label], 2), ws.cell(rows[label], 3)
        print(f"  {b.coordinate:4} {label:22} {b.value!s:22} {b.style:8} {b.number_format:11} | {c.value}")

    choice = ws.cell(rows["Base-case beta choice"], 2).value
    wacc = evaluate(ws, ws.cell(rows["WACC"], 2).coordinate, {}, {})
    shown = excel_display(wacc, 4)
    ok = choice == EXPECTED_CHOICE and shown == EXPECTED_WACC
    print(f"\n== Base-case beta choice = {choice!r}; WACC evaluates to {wacc!r}, "
          f"Excel displays {shown:.2%} -> {'OK' if ok else 'CHECK'}")

    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    outside = [k for k in changed if k not in targets]
    print(f"\n== Cells changed: {[k[1] for k in changed]}")
    print(f"   outside the listed Inputs cells (all tabs): {outside or 'none'}")
    if outside or not ok:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
