"""Build the forward DCF (FCFF method) on the DCF tab, driven entirely by Inputs.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it) and fills the
DCF tab: Year 0 (TTM Jun-26), Years 1-10, Year 11 (terminal). Every number is a
live formula on Inputs cells, found by label; no assumption is typed into a
formula. Header cells hold the year number t (0-11) so the
fade and discounting formulas can use it.

Refuses to run if the workbook is open in Excel or the DCF tab already has a
model. Excel isn't available, so formulas are evaluated in Python: checks
against expected values, an input-change test, and a diff of the workbook.

Usage:
    python scripts/build_dcf.py
"""

import re
import sys
from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from build_bridge import _iferror
from build_wacc import snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SHEET, INPUTS = "DCF", "Inputs"

YEARS = 10
HEADER_ROW, PERIOD_ROW, FIRST_ROW = 4, 5, 6
USD_M, PCT, TAKE, DF, PER_SHARE, MULT = "#,##0", "0.0%", "0.00%", "0.0000", "$0.00", '0.0"x"'
LABEL = "USD m (years to Jun 30)"

# Inputs cells used, by label
I_LABELS = {
    "rev0": "Starting revenue (TTM)", "gmv0": "TTM GMV", "take0": "TTM take rate", "margin0": "TTM EBIT margin",
    "g1": "GMV growth, year 1", "g10": "GMV growth, year 10", "take_inc": "Take rate increase per year",
    "margin10": "Terminal EBIT margin (year 10)", "tax1": "Tax rate, year 1", "tax10": "Tax rate, year 10",
    "da": "D&A % of revenue", "capex": "Capex % of revenue", "wc": "Working capital % of revenue increase",
    "loans": "Loan book % of revenue increase", "flag": "SBC deduction flag", "sbc": "SBC % of revenue (forecast)",
    "tg": "Terminal growth rate", "years": "Forecast years", "wacc": "WACC",
    "nonop": "Net non-operating assets", "shares": "Diluted shares outstanding", "price": "Share price",
    "implied_ev": "Implied enterprise value",
}

EXPECTED = {  # from the brief; tolerance 0.5% (value per share: $0.05)
    ("GMV", 1): 557_492, ("Revenue", 1): 17_229, ("EBIT", 1): 2_586, ("NOPAT", 1): 2_094,
    ("FCFF", 1): 1_144, ("PV of FCFF", 1): 1_036, ("Revenue", 10): 72_670, ("EBIT", 10): 18_167,
    ("FCFF", 10): 12_567, ("FCFF", 11): 13_698,
    "Terminal value": 185_361, "PV of terminal value": 68_980, "Sum of PV (years 1–10)": 29_622,
    "Enterprise value": 98_601, "Equity value": 108_403, "Value per share": 84.03,
    "TV % of EV": 0.700, "TV / year-10 EBIT": 10.2,
}


def period_label(t):
    if t == 0:
        return "TTM Jun-26"
    return f"Jul {2025 + t}–Jun {2026 + t}" + (" (terminal)" if t == YEARS + 1 else "")


# ------------------------------------------------------------ evaluation

REF = re.compile(r"(?:([A-Za-z]+)!)?\$?([A-Z]{1,3})\$?(\d+)")
RANGE = re.compile(r"(?:([A-Za-z]+)!)?\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)")


def _expand(m):
    from openpyxl.utils import column_index_from_string as idx
    sheet = f"{m.group(1)}!" if m.group(1) else ""
    c1, r1, c2, r2 = idx(m.group(2)), int(m.group(3)), idx(m.group(4)), int(m.group(5))
    cells = [f"{sheet}{get_column_letter(c)}{r}" for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
    return ",".join(cells)


def evaluate(wb, sheet, coord, overrides=None, cache=None):
    """Excel-style evaluation: arithmetic incl. ^, cross-sheet refs, SUM(range), IF,
    IFERROR(x,""), CHOOSE, MATCH, = / <>. Blank = 0; text compares case-insensitively."""
    overrides = overrides or {}
    cache = {} if cache is None else cache
    key = (sheet, coord)
    if key in overrides:
        return overrides[key]
    if key in cache:
        return cache[key]
    v = wb[sheet][coord].value
    if isinstance(v, str) and v.startswith("="):
        def ref(m):
            val = evaluate(wb, m.group(1) or sheet, m.group(2) + m.group(3), overrides, cache)
            return "0" if val is None else repr(val.lower() if isinstance(val, str) else val)
        expr = re.sub(r'"[^"]*"', lambda m: m.group(0).lower(), v[1:])
        expr = RANGE.sub(_expand, expr)
        expr = REF.sub(ref, expr).replace("{", "[").replace("}", "]").replace("<>", "!=").replace("^", "**")
        expr = re.sub(r"(?<![<>!=])=(?!=)", "==", expr)
        expr = re.sub(r"IFERROR\(", "IFERROR(lambda: ", expr)
        v = eval(expr, {"__builtins__": {}, "IF": lambda c, a, b: a if c else b,
                        "CHOOSE": lambda i, *xs: xs[int(i) - 1], "MATCH": lambda x, arr, _: arr.index(x) + 1,
                        "IFERROR": _iferror, "SUM": lambda *xs: sum(x for x in xs if isinstance(x, (int, float)))})
    cache[key] = v
    return v


# ------------------------------------------------------------ build

def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws, inp = wb[SHEET], wb[INPUTS]
    if any(ws.cell(r, c).value is not None for r in range(PERIOD_ROW, ws.max_row + 1) for c in range(1, 20)) \
            or isinstance(ws.cell(HEADER_ROW, 2).value, (int, float)):
        sys.exit("DCF tab already has content below the header; not overwriting.")

    i_rows = {inp.cell(r, 1).value: r for r in range(1, inp.max_row + 1) if inp.cell(r, 1).value}
    missing = [l for l in I_LABELS.values() if l not in i_rows]
    if missing:
        sys.exit(f"Inputs rows not found: {missing}")
    I = {k: f"{INPUTS}!$B${i_rows[label]}" for k, label in I_LABELS.items()}

    col = {t: get_column_letter(2 + t) for t in range(YEARS + 2)}  # t=0 -> B ... t=11 -> M
    last_col = 2 + YEARS + 1
    header_style = ws.cell(HEADER_ROW, 1)._style

    # Header: year number (displayed "Year t"), period labels
    ws.cell(HEADER_ROW, 1).value = LABEL
    for t in range(YEARS + 2):
        c = ws[f"{col[t]}{HEADER_ROW}"]
        c._style = copy(header_style)  # a shared StyleArray would make one cell's format change them all
        c.value = t
        c.number_format = "0"  # plain year number; '"Year "0' shows ######## at 13-wide columns
        p = ws[f"{col[t]}{PERIOD_ROW}"]
        p._style = copy(header_style)
        p.value = period_label(t)
    ws.cell(PERIOD_ROW, 1)._style = copy(header_style)
    ws.cell(PERIOD_ROW, 1).value = "Period"
    T = lambda t: f"{col[t]}${HEADER_ROW}"

    rows, r = {}, [FIRST_ROW]

    def section(label):
        for c in range(1, last_col + 1):
            ws.cell(r[0], c).style = "Section"
        ws.cell(r[0], 1).value = label
        r[0] += 1

    def line(label, fmt, formula_for, years, style_for=lambda t: "Formula"):
        """formula_for(t) -> formula string; written for each t in years."""
        row = r[0]
        rows[label] = row  # registered first: some rows refer to their own previous year
        ws.cell(row, 1).value = label
        for t in years:
            c = ws[f"{col[t]}{row}"]
            c.value, c.style, c.number_format = formula_for(t), style_for(t), fmt
        r[0] += 1
        return row

    at = lambda label, t: f"{col[t]}{rows[label]}"
    prev = lambda label, t: f"{col[t - 1]}{rows[label]}"
    FC = range(1, YEARS + 1)              # forecast years 1-10
    FC11 = range(1, YEARS + 2)            # incl. terminal year
    ALL = range(0, YEARS + 2)
    link0 = lambda t: "Link" if t == 0 else "Formula"

    section("Revenue build")
    line("GMV growth", PCT, lambda t: f"={I['g1']}+({I['g10']}-{I['g1']})*({T(t)}-1)/({I['years']}-1)", FC)
    line("GMV", USD_M, lambda t: f"={I['gmv0']}" if t == 0 else f"={prev('GMV', t)}*(1+{at('GMV growth', t)})",
         range(0, YEARS + 1), link0)
    line("Take rate", TAKE, lambda t: f"={I['take0']}+{I['take_inc']}*{T(t)}", range(0, YEARS + 1))
    line("Revenue", USD_M, lambda t: f"={I['rev0']}" if t == 0 else
         f"={prev('Revenue', t)}*(1+{I['tg']})" if t == YEARS + 1 else
         f"={at('GMV', t)}*{at('Take rate', t)}", ALL, link0)
    line("Revenue growth %", PCT, lambda t: f"={at('Revenue', t)}/{prev('Revenue', t)}-1", FC11)

    section("Operating profit")
    line("EBIT margin", PCT, lambda t: f"={prev('EBIT margin', t)}" if t == YEARS + 1 else
         f"={I['margin0']}+({I['margin10']}-{I['margin0']})*{T(t)}/{I['years']}", ALL)
    line("EBIT", USD_M, lambda t: f"={at('Revenue', t)}*{at('EBIT margin', t)}", ALL)
    line("Tax rate", PCT, lambda t: f"={prev('Tax rate', t)}" if t == YEARS + 1 else
         f"={I['tax1']}+({I['tax10']}-{I['tax1']})*({T(t)}-1)/({I['years']}-1)", FC11)
    line("NOPAT", USD_M, lambda t: f"={at('EBIT', t)}*(1-{at('Tax rate', t)})", FC11)

    section("Reinvestment and free cash flow to the firm")
    line("+ D&A", USD_M, lambda t: f"={I['da']}*{at('Revenue', t)}", FC11)
    line("− Capex", USD_M, lambda t: f"={I['capex']}*{at('Revenue', t)}", FC11)
    line("Revenue increase", USD_M, lambda t: f"={at('Revenue', t)}-{prev('Revenue', t)}", FC11)
    line("− Working capital investment", USD_M, lambda t: f"={I['wc']}*{at('Revenue increase', t)}", FC11)
    line("− Loan book investment", USD_M, lambda t: f"={I['loans']}*{at('Revenue increase', t)}", FC11)
    line("+ SBC add-back", USD_M, lambda t: f"=(1-{I['flag']})*{I['sbc']}*{at('Revenue', t)}", FC11)
    line("FCFF", USD_M, lambda t: (f"={at('NOPAT', t)}+{at('+ D&A', t)}-{at('− Capex', t)}"
                                   f"-{at('− Working capital investment', t)}-{at('− Loan book investment', t)}"
                                   f"+{at('+ SBC add-back', t)}"), FC11)
    line("FCFF margin", PCT, lambda t: f"={at('FCFF', t)}/{at('Revenue', t)}", FC11)

    section("Discounting")
    line("Discount factor", DF, lambda t: f"=1/(1+{I['wacc']})^{T(t)}", FC)
    line("PV of FCFF", USD_M, lambda t: f"={at('FCFF', t)}*{at('Discount factor', t)}", FC)

    # Valuation and sanity checks: label in A, value in B
    B = col[0]
    vrows = {}

    def value(label, formula, fmt, style="Formula"):
        row = r[0]
        ws.cell(row, 1).value = label
        c = ws[f"{B}{row}"]
        c.value, c.style, c.number_format = formula, style, fmt
        vrows[label] = f"{B}{row}"
        r[0] += 1

    first_pv, last_pv = at("PV of FCFF", 1), at("PV of FCFF", YEARS)
    section("Valuation")
    value("Sum of PV (years 1–10)", f"=SUM({first_pv}:{last_pv})", USD_M)
    value("Terminal value", f"={at('FCFF', YEARS + 1)}/({I['wacc']}-{I['tg']})", USD_M)
    value("PV of terminal value", f"={vrows['Terminal value']}*{at('Discount factor', YEARS)}", USD_M)
    value("Enterprise value", f"={vrows['Sum of PV (years 1–10)']}+{vrows['PV of terminal value']}", USD_M)
    value("+ Net non-operating assets", f"={I['nonop']}", USD_M, "Link")
    value("Equity value", f"={vrows['Enterprise value']}+{vrows['+ Net non-operating assets']}", USD_M)
    value("÷ Diluted shares (m)", f"={I['shares']}", "#,##0.0", "Link")
    value("Value per share", f"={vrows['Equity value']}/{vrows['÷ Diluted shares (m)']}", PER_SHARE)
    ws.cell(int(vrows["Value per share"][1:]), 1).font = Font(bold=True)
    ws[vrows["Value per share"]].font = Font(bold=True, color="000000")
    value("Current share price", f"={I['price']}", PER_SHARE, "Link")
    value("Upside / (downside) vs price", f"={vrows['Value per share']}/{vrows['Current share price']}-1", PCT)

    section("Sanity checks")
    value("TV % of EV", f"={vrows['PV of terminal value']}/{vrows['Enterprise value']}", PCT)
    value("TV / year-10 EBIT", f"={vrows['Terminal value']}/{at('EBIT', YEARS)}", MULT)
    value("TV / year-10 FCFF", f"={vrows['Terminal value']}/{at('FCFF', YEARS)}", MULT)
    value("Year-10 revenue ÷ TTM revenue", f"={at('Revenue', YEARS)}/{at('Revenue', 0)}", MULT)
    value("Year-10 GMV ÷ TTM GMV", f"={at('GMV', YEARS)}/{at('GMV', 0)}", MULT)
    value("Market-implied EV (Inputs)", f"={I['implied_ev']}", USD_M, "Link")
    value("Model EV ÷ market-implied EV", f"={vrows['Enterprise value']}/{vrows['Market-implied EV (Inputs)']}", MULT)

    ws.column_dimensions[get_column_letter(last_col)].width = ws.column_dimensions["L"].width or 13
    ws.freeze_panes = f"B{PERIOD_ROW + 1}"

    wb.save(WORKBOOK)
    report(before, rows, vrows, col, i_rows)


def report(before, rows, vrows, col, i_rows):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]
    ev = lambda coord, ov=None: evaluate(wb, SHEET, coord, ov)

    print("== DCF (USD m)")
    print(f"  {'':30}" + "".join(f"{('Y' + str(t)):>9}" for t in range(YEARS + 2)))
    for label, row in rows.items():
        cells = []
        for t in range(YEARS + 2):
            c = ws[f"{col[t]}{row}"]
            v = ev(c.coordinate) if c.value is not None else None
            cells.append(f"{'':>9}" if v is None else f"{v:>9.2%}" if c.number_format == TAKE else
                         f"{v:>9.1%}" if c.number_format == PCT else f"{v:>9.4f}" if c.number_format == DF else
                         f"{v:>9,.0f}")
        print(f"  {label[:30]:30}" + "".join(cells))
    print()
    for label, coord in vrows.items():
        c = ws[coord]
        v = ev(coord)
        shown = f"${v:,.2f}" if c.number_format == PER_SHARE else f"{v:.1%}" if c.number_format == PCT else \
            f"{v:.2f}x" if c.number_format == MULT else f"{v:,.1f}" if c.number_format == "#,##0.0" else f"{v:,.0f}"
        print(f"  {label:34} {shown:>12}   {c.value}")

    print("\n== Checks vs expected (0.5%; value per share $0.05)")
    ok = True
    for key, expected in EXPECTED.items():
        if isinstance(key, tuple):
            label, t = key
            got = ev(f"{col[t]}{rows[label]}")
            name = f"{label}, year {t}"
        else:
            got, name = ev(vrows[key]), key
        good = abs(got - expected) <= 0.05 if key == "Value per share" else abs(got / expected - 1) <= 0.005
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {name:32} {got:>14,.4f} vs {expected:,}  ({got / expected - 1:+.3%})")
    y1 = ev(f"{col[1]}{rows['− Working capital investment']}") + ev(f"{col[1]}{rows['− Loan book investment']}")
    good = abs(y1 / 950 - 1) <= 0.005
    ok &= good
    print(f"  {'OK  ' if good else 'FAIL'} Reinvestment (WC + loans), year 1 {y1:,.1f} vs 950")

    vps = vrows["Value per share"]
    m10 = (INPUTS, f"B{i_rows['Terminal EBIT margin (year 10)']}")
    treat = (INPUTS, f"B{i_rows['SBC treatment']}")
    t30 = ev(vps, {m10: 0.30})
    ign = ev(vps, {treat: "ignore"})
    print(f"\n== Input-change tests (evaluated with the input changed; workbook keeps the base case)")
    print(f"  Terminal EBIT margin 30%: value per share ${t30:,.2f} (expected ≈ $99.38) "
          f"{'OK' if abs(t30 - 99.38) <= 0.05 else 'CHECK'}")
    print(f"  SBC treatment = ignore:  value per share ${ign:,.2f}")
    print(f"  Base case (25%, subtract): ${ev(vps):,.2f}; workbook inputs unchanged: "
          f"{wb[INPUTS][m10[1]].value} / {wb[INPUTS][treat[1]].value}")

    tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print(f"\n== Tabs changed by this script: {tabs}; freeze panes {ws.freeze_panes}")
    if tabs != [SHEET]:
        sys.exit("Something outside the DCF tab changed")
    if not ok:
        print("\nSome checks are outside tolerance; see above.")


if __name__ == "__main__":
    main()
