"""Set up the reverse DCF: growth override on Inputs, override-aware DCF, Reverse tab layout.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it):
- Inputs, end of "DCF assumptions": "GMV growth override (constant, all 10 years)",
  blue input left blank.
- DCF, GMV growth row: =IF(ISBLANK(override), <existing fade>, override). With the
  override blank every result is unchanged.
- Reverse tab: Goal Seek block (live), Results block (filled by scripts/reverse.py),
  Comparison block (formulas).
Rows are found by label; refuses to run if the workbook is open in Excel or the
override already exists. Diffs the workbook and re-evaluates every DCF cell.

Usage:
    python scripts/build_reverse.py
    python scripts/reverse.py      # then solve and fill the Results block
"""

import re
import sys
from pathlib import Path

from openpyxl import load_workbook

from build_dcf import OVERRIDE, evaluate
from build_wacc import snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
INPUTS, DCF, REV, HIST = "Inputs", "DCF", "Reverse", "Historicals"
PCT, USD_M, MULT, PER_SHARE = "0.0%", "#,##0", '0.0"x"', "$0.00"
OVERRIDE_NOTE = "Blank = use the 29% → 7% fade. Set by Goal Seek in the reverse DCF."
BLOCK_LAST = "Loan book % of revenue increase"

# Results written by reverse.py: (label, format)
RESULTS = [
    ("(a) Implied constant GMV growth (10 years)", PCT),
    ("(b) Base-case-equivalent constant GMV growth", PCT),
    ("(c) Implied terminal EBIT margin (year 10)", PCT),
    ("(d) Implied year-1 GMV growth (fading to 7%)", PCT),
    ("(a) Year-10 GMV", USD_M),
    ("(a) Year-10 revenue", USD_M),
    ("(a) Year-10 GMV ÷ TTM GMV", MULT),
    ("(a) Year-10 revenue ÷ TTM revenue", MULT),
    ("(a) Year-10 FCFF", USD_M),
]
PAYPAL = ("PayPal GAAP operating margin, FY2025", 0.183,
          "PayPal FY2025 GAAP operating margin, Q4 2025 earnings release (Feb 2026)")
DESCRIPTION = "Solve for the constant GMV growth rate that makes value per share = current price."


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    inp, dcf, rev, hist = wb[INPUTS], wb[DCF], wb[REV], wb[HIST]
    i_rows = {inp.cell(r, 1).value: r for r in range(1, inp.max_row + 1) if inp.cell(r, 1).value}
    if OVERRIDE in i_rows:
        sys.exit("Override already exists; nothing to do.")
    r = i_rows[BLOCK_LAST] + 1
    # check without inp.cell(), which would create empty cells and move max_row
    if r <= max(i_rows.values()) or any(inp._cells.get((rr, c)) is not None and inp._cells[(rr, c)].value is not None
                                       for rr in range(r, r + 5) for c in (1, 2, 3)):
        sys.exit(f"{BLOCK_LAST!r} is not the last Inputs row; not appending.")
    if any(rev.cell(r, c).value is not None for r in range(5, rev.max_row + 2) for c in range(1, 4)):
        sys.exit("Reverse tab already has content below the header.")

    d_rows = {dcf.cell(r, 1).value: r for r in range(1, dcf.max_row + 1) if dcf.cell(r, 1).value}
    dcf_before = {c.coordinate: evaluate(wb, DCF, c.coordinate) for row in dcf.iter_rows() for c in row
                  if isinstance(c.value, str) and c.value.startswith("=")}

    # 1. Override row on Inputs (blank blue input), directly after the block
    i_rows[OVERRIDE] = r
    inp.cell(r, 1, OVERRIDE)
    c = inp.cell(r, 2)
    c.style, c.number_format = "Input", PCT
    inp.cell(r, 3, OVERRIDE_NOTE)
    ov = f"{INPUTS}!$B${r}"

    # 2. DCF GMV growth: IF(ISBLANK(override), fade, override)
    g = d_rows["GMV growth"]
    rewritten = 0
    for cell in dcf[g][1:]:
        if isinstance(cell.value, str) and cell.value.startswith("=") and "ISBLANK" not in cell.value:
            cell.value = f"=IF(ISBLANK({ov}),{cell.value[1:]},{ov})"
            rewritten += 1

    # 3. Reverse tab
    h_header = next(r for r in range(1, hist.max_row + 1) if hist.cell(r, 1).value == "Item")
    h_cols = {hist.cell(h_header, c).value: c for c in range(1, hist.max_column + 1)}
    h_rows = {hist.cell(r, 1).value: r for r in range(h_header + 1, hist.max_row + 1) if hist.cell(r, 1).value}
    hist_ref = lambda label, period: f"={HIST}!{hist.cell(h_rows[label], h_cols[period]).coordinate}"
    rev.cell(2, 1).value = DESCRIPTION
    rev.cell(4, 1).value, rev.cell(4, 2).value, rev.cell(4, 3).value = "Item", "Value", "Notes"
    rev.column_dimensions["C"].width = 90

    rr = {}
    nxt = [5]

    def section(label):
        for col in range(1, 4):
            rev.cell(nxt[0], col).style = "Section"
        rev.cell(nxt[0], 1).value = label
        nxt[0] += 1

    def row(label, value, style, fmt, note=None):
        r = nxt[0]
        rev.cell(r, 1, label)
        c = rev.cell(r, 2)
        c.value, c.style, c.number_format = value, style, fmt
        if note:
            rev.cell(r, 3, note)
        rr[label] = f"B{r}"
        nxt[0] += 1
        return r

    section("Goal Seek (live)")
    row("Target price (current share price)", f"={INPUTS}!$B${i_rows['Share price']}", "Link", PER_SHARE)
    row("Model value per share", f"={DCF}!$B${d_rows['Value per share']}", "Link", PER_SHARE)
    diff = row("Difference (model − target)", f"={rr['Model value per share']}-{rr['Target price (current share price)']}",
               "Formula", PER_SHARE)
    rev.cell(diff, 3).value = (f"Data → What-If Analysis → Goal Seek: Set cell = {REV}!B{diff}, To value = 0, "
                               f"By changing = {INPUTS}!B{i_rows[OVERRIDE]}. Clear the override afterwards.")

    section("Results (scripts/reverse.py)")
    for label, fmt in RESULTS:
        row(label, None, "ToFill", fmt, "Not solved yet: run scripts/reverse.py")

    section("Comparison")
    a, b, cm = rr[RESULTS[0][0]], rr[RESULTS[1][0]], rr[RESULTS[2][0]]
    row("Implied constant GMV growth (a)", f"={a}", "Formula", PCT)
    row("Base-case-equivalent constant growth (b)", f"={b}", "Formula", PCT)
    row("Gap, (a) − (b) (percentage points)", f"={a}-{b}", "Formula", PCT,
        "Extra constant growth the price needs over the base-case fade")
    row("Actual GMV growth, FY2025", hist_ref("GMV growth %", "FY2025"), "Link", PCT, "Historicals")
    row("Actual GMV growth, H1 2026 (vs H1 2025)", hist_ref("GMV growth %", "H1 2026"), "Link", PCT, "Historicals")
    row("(a) − FY2025 actual", f"={a}-{rr['Actual GMV growth, FY2025']}", "Formula", PCT)
    row("(a) − H1 2026 actual", f"={a}-{rr['Actual GMV growth, H1 2026 (vs H1 2025)']}", "Formula", PCT)
    row("Implied terminal EBIT margin (c)", f"={cm}", "Formula", PCT)
    row("Base-case terminal EBIT margin", f"={INPUTS}!$B${i_rows['Terminal EBIT margin (year 10)']}", "Link", PCT)
    row(PAYPAL[0], PAYPAL[1], "Input", PCT, PAYPAL[2])
    row("(c) − base case", f"={cm}-{rr['Base-case terminal EBIT margin']}", "Formula", PCT)
    row("(c) − PayPal", f"={cm}-{rr[PAYPAL[0]]}", "Formula", PCT)

    rev.freeze_panes = "A5"
    wb.save(WORKBOOK)
    report(before, dcf_before, rewritten, d_rows, i_rows)


def report(before, dcf_before, rewritten, d_rows, i_rows):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    dcf = wb[DCF]
    dcf_after = {k: evaluate(wb, DCF, k) for k in dcf_before}
    changed_vals = [k for k in dcf_before if dcf_before[k] != dcf_after[k]]
    vps = evaluate(wb, DCF, f"B{d_rows['Value per share']}")
    print(f"DCF GMV growth cells rewritten: {rewritten}; e.g. {dcf.cell(d_rows['GMV growth'], 3).value}")
    print(f"With override blank: value per share ${vps:.2f}; DCF cells whose value changed: {len(changed_vals)}")
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    by_tab = {}
    for s, c in changed:
        by_tab.setdefault(s, []).append(c)
    print("Cells changed by tab:", {s: (cs if len(cs) < 14 else f"{len(cs)} cells") for s, cs in by_tab.items()})
    bad = [s for s in by_tab if s not in (INPUTS, DCF, REV)]
    if bad or changed_vals or abs(vps - 84.10) > 0.005:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
