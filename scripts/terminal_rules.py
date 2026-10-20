"""Terminal value with Damodaran Rules 3 & 4, plus ROIC sanity rows.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it):
- Inputs: "Stable period (after year 10)" block at the end: stable beta, stable WACC
  (risk-free + stable beta x MRP, no debt), moat spread, stable ROIC, stable
  reinvestment rate (terminal growth / stable ROIC).
- DCF: a "Total reinvestment" row (capex - D&A + WC + loans; year 11: NOPAT x stable
  reinvestment rate); year 11 FCFF = NOPAT - reinvestment + SBC add-back; terminal
  value = FCFF11 / (stable WACC - terminal growth), discounted with the year-10
  high-growth discount factor. Years 1-10 are unchanged.
- DCF: "ROIC sanity checks" block (years 0-11).
Rows are found by label; inserted rows are handled by wb_rows.insert_rows, which
rewrites every reference in the workbook. Refuses to run if the workbook is open in
Excel or the block already exists. Re-evaluates every DCF cell and diffs.

Usage:
    python scripts/terminal_rules.py
"""

import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from build_dcf import evaluate
from build_wacc import snapshot
from wb_rows import insert_rows

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
INPUTS, DCF, HIST = "Inputs", "DCF", "Historicals"
PCT, PCT2, USD_M, RATIO = "0.0%", "0.00%", "#,##0", "0.00"
SECTION = "Stable period (after year 10)"
YEARS = 10


def block():
    """(label, kind, value or formula with {Label} refs, format, note)."""
    return [
        ("Stable-period beta", "Input", 1.0, RATIO, "Damodaran Session 9, Rule 4: mature firms move toward average risk"),
        ("Stable-period WACC", "Formula", "={Risk-free rate}+{Stable-period beta}*{Market risk premium}", PCT2,
         "Risk-free + stable beta × MRP (no debt)"),
        ("Moat spread over stable WACC", "Input", 0.02, PCT,
         "Damodaran: moat firms earn 2–3% above WACC. Switching costs + ecosystem; lower end given competition "
         "(Amazon, WooCommerce, AI agents)"),
        ("Stable ROIC", "Formula", "={Stable-period WACC}+{Moat spread over stable WACC}", PCT2, "Stable WACC + moat spread"),
        ("Stable reinvestment rate", "Formula", '=IFERROR({Terminal growth rate}/{Stable ROIC},"")', PCT,
         "Rule 3: growth must be paid for (terminal growth / stable ROIC)"),
    ]


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    inp, d, hist = wb[INPUTS], wb[DCF], wb[HIST]
    i_rows = {inp.cell(r, 1).value: r for r in range(1, inp.max_row + 1) if inp.cell(r, 1).value}
    if SECTION in i_rows:
        sys.exit(f"{SECTION!r} already exists; nothing to do.")
    d_rows = {d.cell(r, 1).value: r for r in range(1, d.max_row + 1) if d.cell(r, 1).value}
    vals_before = {(r, c): evaluate(wb, DCF, d.cell(r, c).coordinate) for r in range(6, d.max_row + 1)
                   for c in range(2, 14) if isinstance(d.cell(r, c).value, str) and d.cell(r, c).value.startswith("=")}

    # ---- Inputs: stable-period block at the end
    last = max(i_rows.values())
    section_like = next(r for r in i_rows.values() if inp.cell(r, 1).style == "Section")
    r = last + 1
    for col in (1, 2, 3):
        inp.cell(r, col)._style = inp.cell(section_like, col)._style.__copy__()
    inp.cell(r, 1).value = SECTION
    spec = block()
    new = {label: r + 1 + k for k, (label, *_) in enumerate(spec)}
    i_rows.update(new)
    ref = lambda label: f"B{i_rows[label]}"
    for label, kind, value, fmt, note in spec:
        rr = new[label]
        inp.cell(rr, 1, label)
        c = inp.cell(rr, 2)
        if kind == "Formula":
            for lab in [l for l in i_rows if "{" + l + "}" in value]:
                value = value.replace("{" + lab + "}", ref(lab))
        c.value, c.style, c.number_format = value, kind, fmt
        inp.cell(rr, 3, note)
    I = lambda label: f"{INPUTS}!$B${i_rows[label]}"

    # ---- DCF: insert "Total reinvestment" after "+ SBC add-back"
    at = d_rows["+ SBC add-back"] + 1
    n_changed = insert_rows(wb, DCF, at, 1)
    d_rows = {d.cell(r, 1).value: r for r in range(1, d.max_row + 1) if d.cell(r, 1).value}
    col = {t: get_column_letter(2 + t) for t in range(YEARS + 2)}
    R = lambda label, t: f"{col[t]}{d_rows[label]}"
    reinv = at
    d.cell(reinv, 1).value = "Total reinvestment"
    d_rows["Total reinvestment"] = reinv
    for t in range(1, YEARS + 2):
        c = d[f"{col[t]}{reinv}"]
        if t <= YEARS:
            c.value = (f"={R('− Capex', t)}-{R('+ D&A', t)}+{R('− Working capital investment', t)}"
                       f"+{R('− Loan book investment', t)}")
        else:
            c.value = f"={R('NOPAT', t)}*{I('Stable reinvestment rate')}"
        c.style, c.number_format = "Formula", USD_M
    t11 = YEARS + 1
    for label in ("+ D&A", "− Capex", "− Working capital investment", "− Loan book investment"):
        c = d[R(label, t11)]
        c.value = None
        c.style = "Normal"
    d[R("FCFF", t11)].value = f"={R('NOPAT', t11)}-{R('Total reinvestment', t11)}+{R('+ SBC add-back', t11)}"
    tv = f"B{d_rows['Terminal value']}"
    d[tv].value = f"={R('FCFF', t11)}/({I('Stable-period WACC')}-{I('Terminal growth rate')})"
    nop0 = d[R("NOPAT", 0)]
    nop0.value = f"={R('EBIT', 0)}*(1-{I('Tax rate, year 1')})"
    nop0.style, nop0.number_format = "Formula", USD_M

    # ---- DCF: ROIC sanity checks at the end
    h_header = next(r for r in range(1, hist.max_row + 1) if hist.cell(r, 1).value == "Item")
    h_cols = {hist.cell(h_header, c).value: c for c in range(1, hist.max_column + 1)}
    h_rows = {hist.cell(r, 1).value: r for r in range(h_header + 1, hist.max_row + 1) if hist.cell(r, 1).value}
    H = lambda label: f"{HIST}!{hist.cell(h_rows[label], h_cols['TTM Jun-26']).coordinate}"
    rr = [d.max_row + 1]

    def section(title):
        for cc in range(1, 2 + YEARS + 2):
            d.cell(rr[0], cc).style = "Section"
        d.cell(rr[0], 1).value = title
        rr[0] += 1

    def line(label, fmt, formula_for, years):
        row = rr[0]
        d_rows[label] = row
        d.cell(row, 1).value = label
        for t in years:
            c = d[f"{col[t]}{row}"]
            c.value, c.style, c.number_format = formula_for(t), "Formula", fmt
        rr[0] += 1
        return row

    section("ROIC sanity checks")
    line("Reinvestment rate (reinvestment ÷ NOPAT)", PCT,
         lambda t: (f"=({H('Capex (purchases of property & equipment)')}-{H('Amortization and depreciation')}"
                    f"+{H('ΔNWC (+ = cash used)')}+{H('Change in net loan book')})/{R('NOPAT', 0)}") if t == 0
         else f"={R('Total reinvestment', t)}/{R('NOPAT', t)}", range(0, YEARS + 2))
    line("Sales-to-capital (1 ÷ (WC % + loan %))", RATIO,
         lambda t: f"=1/({I('Working capital % of revenue increase')}+{I('Loan book % of revenue increase')})",
         range(1, YEARS + 1))
    line("ROIC on new capital (after-tax margin × sales-to-capital)", PCT,
         lambda t: f"={R('EBIT margin', t)}*(1-{R('Tax rate', t)})*{R('Sales-to-capital (1 ÷ (WC % + loan %))', t)}",
         range(1, YEARS + 1))
    line("Measured incremental ROIC (ΔNOPAT ÷ reinvestment)", PCT,
         lambda t: f"=({R('NOPAT', t)}-{col[t - 1]}{d_rows['NOPAT']})/{R('Total reinvestment', t)}", range(1, YEARS + 1))
    line("Implied stable ROIC (terminal growth ÷ reinvestment rate)", PCT2,
         lambda t: f"={I('Terminal growth rate')}/{R('Reinvestment rate (reinvestment ÷ NOPAT)', t)}", [t11])
    line("Check: implied − Inputs stable ROIC", PCT2,
         lambda t: f"={R('Implied stable ROIC (terminal growth ÷ reinvestment rate)', t)}-{I('Stable ROIC')}", [t11])
    line("Step-down: FCFF₁₁ − FCFF₁₀", USD_M, lambda t: f"={R('FCFF', t)}-{R('FCFF', t - 1)}", [t11])
    line("FCFF₁₁ ÷ FCFF₁₀", '0.00"x"', lambda t: f"={R('FCFF', t)}/{R('FCFF', t - 1)}", [t11])

    wb.save(WORKBOOK)
    report(before, vals_before, at, n_changed)


def report(before, vals_before, at, n_changed):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    d, inp = wb[DCF], wb[INPUTS]
    ev = lambda s, c: evaluate(wb, s, c)
    i_rows = {inp.cell(r, 1).value: r for r in range(1, inp.max_row + 1) if inp.cell(r, 1).value}
    d_rows = {d.cell(r, 1).value: r for r in range(1, d.max_row + 1) if d.cell(r, 1).value}
    print(f"Inserted 1 DCF row at {at}; formulas rewritten across the workbook: {n_changed}")
    print("Inputs stable block:", {l: round(ev(INPUTS, f'B{i_rows[l]}'), 6) for l in
                                   ("Stable-period beta", "Stable-period WACC", "Moat spread over stable WACC",
                                    "Stable ROIC", "Stable reinvestment rate")})
    # years 1-10 unchanged (rows moved by one from 'at')
    unchanged, changed = 0, []
    for (r, c), old in vals_before.items():
        r2 = r + (1 if r >= at else 0)
        new = ev(DCF, d.cell(r2, c).coordinate)
        if new == old:
            unchanged += 1
        else:
            changed.append((d.cell(r2, 1).value, get_column_letter(c), old, new))
    print(f"DCF formula cells unchanged: {unchanged}; changed: {len(changed)}")
    for lab, c, old, new in changed:
        print(f"   {lab[:34]:34} {c}: {old:,.4f} -> {new:,.4f}" if isinstance(new, float) and isinstance(old, float)
              else f"   {lab[:34]:34} {c}: {old} -> {new}")
    print("ROIC block:")
    for lab in [l for l in d_rows if d_rows[l] > d_rows["Model EV ÷ market-implied EV"]]:
        r = d_rows[lab]
        vals = [d.cell(r, c) for c in range(2, 14)]
        print(f"   {lab[:58]:58}", " ".join("" if c.value is None else f"{ev(DCF, c.coordinate):.3f}" for c in vals))
    print("Reverse!B7:", wb["Reverse"]["B7"].value, "| Scenarios!B25:", wb["Scenarios"]["B25"].value,
          "| Inputs!B80 blank:", inp["B80"].value is None)
    tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print("Tabs changed:", tabs)


if __name__ == "__main__":
    main()
