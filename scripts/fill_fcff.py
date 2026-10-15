"""Add an FCFF build to the Historicals tab (below Ratios), from data/cash_flow.csv.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it) and appends two
sections under Ratios, so no existing row moves:
- "FCFF data": blue inputs with source comments (pre-tax income, tax provision,
  cash taxes, D&A, every change in operating assets & liabilities, Shopify Capital
  loan lines). Cash-flow lines keep the statement's signs (outflows negative).
- "FCFF build": black formulas on the rows above:
  FCFF = EBIT x (1 - cash tax rate) + D&A - capex - change in NWC.
Rows are found by label in column A, columns by the header row.

Refuses to run if the workbook is open in Excel or the sections already exist.
Evaluates every new formula in Python and diffs the workbook before vs after.

Usage:
    python scripts/fill_fcff.py
"""

import csv
import sys
from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font

from build_bridge import evaluate
from build_wacc import snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
CF_CSV = ROOT / "data" / "cash_flow.csv"
SHEET, INPUTS = "Historicals", "Inputs"

PERIODS = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "H1 2025", "H1 2026"]
TTM = "TTM Jun-26"
COLS = PERIODS + [TTM]
FY = PERIODS[:5]
PRIOR = {"FY2022": "FY2021", "FY2023": "FY2022", "FY2024": "FY2023", "FY2025": "FY2024", "H1 2026": "H1 2025"}
USD_M, PCT, GREY = "#,##0", "0.0%", "808080"

DATA_SECTION = "FCFF data (cash flow statement; outflows negative)"
BUILD_SECTION = "FCFF build"

# Historicals rows used (by label)
REV, EBIT_SRC, CAPEX, FCF, SBC = ("Total revenue", "Operating income",
                                  "Capex (purchases of property & equipment)", "Free cash flow",
                                  "Stock-based compensation")
INPUTS_INTEREST = "TTM interest income (after tax)"

# Data rows: (row label, csv section, csv key, note). key = xbrl tag or "other" line name.
OTHER = [
    ("Income before income taxes", "other", "Income before income taxes", "Income statement"),
    ("Provision for income taxes", "other", "Provision for income taxes", "Income statement"),
    ("Cash paid for income taxes, net", "other", "Cash paid for income taxes, net",
     "Supplemental cash flow information"),
    ("Amortization and depreciation", "non_cash", "us-gaap:DepreciationDepletionAndAmortization",
     "Cash flow statement, total D&A"),
    ("Amortization of acquired intangibles", "other", "Amortization of acquired intangibles",
     "Memo: intangibles note; not in the Jun-2026 10-Q"),
]
TOTAL_TAG = "us-gaap:IncreaseDecreaseInOtherOperatingCapitalNet"
CHANGES_TOTAL = "Changes in operating assets and liabilities (total)"
LOANS = [
    ("Purchases and originations of loans (+ MCAs from Apr 2026)",
     "us-gaap:PaymentsToAcquireLoansHeldForInvestment"),
    ("Repayments and sales of loans (+ MCAs from Apr 2026)",
     "us-gaap:ProceedsFromPrincipalRepaymentsOnLoansAndLeasesHeldForInvestment"),
]
MCA_TAG = "us-gaap:IncreaseDecreaseInFinanceReceivables"
NA_H1 = "Not disclosed: the 10-Q shows only the total change in operating assets and liabilities."


def load_cf():
    with CF_CSV.open() as fh:
        rows = list(csv.DictReader(fh))
    data = {}
    for r in rows:
        key = r["line"] if r["section"] == "other" else r["xbrl_tag"]
        data[(r["section"], key, r["period"])] = r
    # Detail lines of the operating changes, in the order of the latest statement, then older-only ones
    changes = []
    for p in reversed(PERIODS):
        for r in rows:
            if r["period"] == p and r["section"] == "op_change" and r["xbrl_tag"] != TOTAL_TAG \
                    and r["xbrl_tag"] not in [t for t, _ in changes]:
                changes.append((r["xbrl_tag"], r["line"]))
    return data, changes


def comment(r):
    c = Comment(f"Source: SEC XBRL\nForm: {r['form']}\nAccession: {r['accession_number']}\n"
                f"Period end: {r['period_end']}\nTag: {r['xbrl_tag']}\nLine: {r['line']}", "fill_fcff.py")
    c.width, c.height = 340, 150
    return c


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    data, changes = load_cf()
    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws = wb[SHEET]

    header = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Item")
    cols = {ws.cell(header, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(header, c).value}
    notes_col = cols["Source / notes"]
    rows = {ws.cell(r, 1).value: r for r in range(header + 1, ws.max_row + 1) if ws.cell(r, 1).value}
    if DATA_SECTION in rows:
        sys.exit("FCFF sections already exist; nothing to do.")
    section_like = next(r for r in rows.values() if ws.cell(r, 1).style == "Section")
    last = max(rows.values())
    if any(ws.cell(r, c).value is not None for r in range(last + 1, last + 80) for c in range(1, notes_col + 1)):
        sys.exit("Rows below the Ratios section are not empty; not writing over them.")
    inp = wb[INPUTS]
    inputs_rows = {inp.cell(r, 1).value: r for r in range(1, inp.max_row + 1) if inp.cell(r, 1).value}

    L = {p: ws.cell(1, cols[p]).column_letter for p in COLS}
    next_row = [last + 1]
    added = {}

    def new_row(label, note=None):
        r = next_row[0]
        next_row[0] += 1
        ws.cell(r, 1, label)
        if note:
            ws.cell(r, notes_col, note)
        added[label] = r
        rows[label] = r
        return r

    def section(label):
        r = new_row(label)
        for c in range(1, notes_col + 1):
            ws.cell(r, c)._style = copy(ws.cell(section_like, c)._style)

    def cell(r, p, value, style, fmt):
        c = ws.cell(r, cols[p])
        c.value, c.style, c.number_format = value, style, fmt
        return c

    def na(r, p, note=None, fmt=USD_M):
        c = cell(r, p, "n/a", "Formula", fmt)
        c.font, c.alignment = Font(color=GREY), Alignment(horizontal="right")
        if note:
            c.comment = Comment(note, "fill_fcff.py")
        return c

    def ttm_flow(r, fmt=USD_M):
        cell(r, TTM, f"={L['FY2025']}{r}+{L['H1 2026']}{r}-{L['H1 2025']}{r}", "Formula", fmt)

    def put_input(r, p, src):
        c = cell(r, p, float(src["value"]), "Input", USD_M)
        c.comment = comment(src)

    # ---------------- FCFF data
    section(DATA_SECTION)
    for label, sec, key, note in OTHER:
        r = new_row(label, note)
        for p in PERIODS:
            src = data.get((sec, key, p))
            if src and src["value"] != "":
                put_input(r, p, src)
            else:
                ws.cell(r, cols[p]).style = "ToFill"
                ws.cell(r, cols[p]).number_format = USD_M
                ws.cell(r, cols[p]).comment = Comment("Not found in XBRL for this period; left blank.", "fill_fcff.py")
        if all(data.get((sec, key, p), {}).get("value", "") != "" for p in ("FY2025", "H1 2025", "H1 2026")):
            ttm_flow(r)
        else:
            na(r, TTM, "TTM needs FY2025, H1 2025 and H1 2026; at least one is not disclosed.")

    detail_rows = []
    for tag, line in changes:
        r = new_row(line, "Change in operating assets & liabilities (CF statement)")
        detail_rows.append(r)
        for p in FY:
            src = data.get(("op_change", tag, p))
            if src:
                put_input(r, p, src)
        for p in ("H1 2025", "H1 2026"):
            na(r, p, NA_H1)
        na(r, TTM, NA_H1)
    r = new_row(CHANGES_TOTAL, "FY: sum of the lines above; H1: single line in the 10-Q")
    for p in FY:
        cell(r, p, "=" + "+".join(f"{L[p]}{d}" for d in detail_rows), "Formula", USD_M)
    for p in ("H1 2025", "H1 2026"):
        put_input(r, p, data[("op_change", TOTAL_TAG, p)])
    ttm_flow(r)

    for label, tag in LOANS:
        r = new_row(label, "Investing activities (Shopify Capital)")
        for p in PERIODS:
            put_input(r, p, data[("shopify_capital_investing", tag, p)])
        ttm_flow(r)

    # ---------------- FCFF build
    section(BUILD_SECTION)
    R = lambda label: rows[label]

    def build(label, formula_for, fmt, note=None, cols_=COLS, na_note=None):
        r = new_row(label, note)
        for p in COLS:
            if p in cols_:
                cell(r, p, formula_for(L[p]), "Formula", fmt)
            else:
                na(r, p, na_note, fmt)
        return r

    build("EBIT", lambda c: f"={c}{R(EBIT_SRC)}", USD_M, "Equals operating income")  # notes must not start with "="
    build("Effective tax rate", lambda c: f'=IFERROR({c}{R("Provision for income taxes")}/{c}{R("Income before income taxes")},"")',
          PCT, "Provision / pre-tax income")
    build("Cash tax rate", lambda c: f'=IFERROR({c}{R("Cash paid for income taxes, net")}/{c}{R("Income before income taxes")},"")',
          PCT, "Cash taxes paid / pre-tax income")
    build("D&A", lambda c: f"={c}{R('Amortization and depreciation')}", USD_M)
    build("D&A % of revenue", lambda c: f'=IFERROR({c}{R("D&A")}/{c}{R(REV)},"")', PCT)
    build("Capex", lambda c: f"={c}{R(CAPEX)}", USD_M, "Positive = cash spent")
    build("Capex % of revenue", lambda c: f'=IFERROR({c}{R("Capex")}/{c}{R(REV)},"")', PCT)
    build("ΔNWC (+ = cash used)", lambda c: f"=-{c}{R(CHANGES_TOTAL)}", USD_M,
          "Minus the CF change in operating assets & liabilities: CF negative = cash used = reinvestment")
    r = new_row("ΔNWC % of revenue change", "ΔNWC / (revenue − prior-period revenue)")
    for p in COLS:
        if p in PRIOR:
            cell(r, p, f'=IFERROR({L[p]}{R("ΔNWC (+ = cash used)")}/({L[p]}{R(REV)}-{L[PRIOR[p]]}{R(REV)}),"")', "Formula", PCT)
        else:
            na(r, p, "No comparable prior period in the workbook.", PCT)
    purch, repay = R(LOANS[0][0]), R(LOANS[1][0])
    build("Shopify Capital: net loans, investing (+ = lent)", lambda c: f"=-({c}{purch}+{c}{repay})", USD_M,
          "Investing section; includes merchant cash advances only from Apr 2026")
    build("Net loans % of revenue", lambda c: f'=IFERROR({c}{R("Shopify Capital: net loans, investing (+ = lent)")}/{c}{R(REV)},"")', PCT)
    mca = next(r for (tag, line), r in zip(changes, detail_rows) if tag == MCA_TAG)
    na_mca = "MCA change not disclosed for H1 periods (inside the single 10-Q total)."
    build("Shopify Capital: net MCAs, operating (+ = advanced)", lambda c: f"=-{c}{mca}", USD_M,
          "Inside ΔNWC through Mar 2026", cols_=FY, na_note=na_mca)
    build("Net Shopify Capital lending", lambda c: f'={c}{R("Shopify Capital: net loans, investing (+ = lent)")}+{c}{R("Shopify Capital: net MCAs, operating (+ = advanced)")}',
          USD_M, "Loans (investing) + MCAs (operating)", cols_=FY, na_note=na_mca)
    build("Net Shopify Capital lending % of revenue", lambda c: f'=IFERROR({c}{R("Net Shopify Capital lending")}/{c}{R(REV)},"")',
          PCT, cols_=FY, na_note=na_mca)
    build("FCFF at cash tax rate",
          lambda c: f'=IFERROR({c}{R("EBIT")}*(1-{c}{R("Cash tax rate")})+{c}{R("D&A")}-{c}{R("Capex")}-{c}{R("ΔNWC (+ = cash used)")},"")',
          USD_M, "EBIT × (1 − cash tax rate) + D&A − capex − ΔNWC")
    build("FCFF margin", lambda c: f'=IFERROR({c}{R("FCFF at cash tax rate")}/{c}{R(REV)},"")', PCT)
    na_ttm = "Comparison is TTM only (after-tax interest is on Inputs for TTM)."
    r = new_row("After-tax interest income (Inputs)", "Link to Inputs, TTM")
    for p in PERIODS:
        na(r, p, na_ttm)
    cell(r, TTM, f"={INPUTS}!B{inputs_rows[INPUTS_INTEREST]}", "Link", USD_M)
    build("FCF − SBC − after-tax interest", lambda c: f'={c}{R(FCF)}-{c}{R(SBC)}-{c}{R("After-tax interest income (Inputs)")}',
          USD_M, "Starting point on Inputs (≈ 1,644 TTM)", cols_=[TTM], na_note=na_ttm)
    build("FCFF − (FCF − SBC − interest)", lambda c: f'={c}{R("FCFF at cash tax rate")}-{c}{R("FCF − SBC − after-tax interest")}',
          USD_M, "Explained in the report", cols_=[TTM], na_note=na_ttm)

    wb.save(WORKBOOK)
    report(before, added)


def report(before, added):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]
    header = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Item")
    cols = {ws.cell(header, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(header, c).value}

    print(f"== New rows {min(added.values())}-{max(added.values())}, evaluated (USD m)")
    print(f"  {'':50}" + "".join(f"{p:>10}" for p in COLS))
    for label, r in added.items():
        if ws.cell(r, 1).style == "Section":
            print(f"  [{label}]")
            continue
        cells = []
        for p in COLS:
            c = ws.cell(r, cols[p])
            v = evaluate(wb, SHEET, c.coordinate) if c.value is not None else None
            if v is None:
                cells.append(f"{'':>10}")
            elif isinstance(v, str):
                cells.append(f"{v or '(blank)':>10}")
            elif c.number_format == PCT:
                cells.append(f"{v:>10.1%}")
            else:
                cells.append(f"{v:>10,.0f}")
        print(f"  {label[:50]:50}" + "".join(cells))

    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    outside = [k for k in changed if not (k[0] == SHEET and k[1] != "_validations"
                                          and int("".join(filter(str.isdigit, k[1]))) >= min(added.values()))]
    print(f"\n== Cells changed: {len(changed)}; outside the new rows (all tabs): {outside or 'none'}")
    if outside:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
