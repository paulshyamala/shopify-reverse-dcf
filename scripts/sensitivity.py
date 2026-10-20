"""Sensitivity and comparison analysis for the reverse and forward DCF.

Reuses load_params(), the DCF replica and the solver from scripts/reverse.py and reads
every assumption from the workbook. Asserts the replica matches the workbook first.
  Grid 1: implied constant GMV growth (value = price), WACC x terminal EBIT margin
  Grid 2: implied constant GMV growth, terminal growth x SBC treatment
  Grid 3: value per share (base growth fade), WACC x terminal EBIT margin
          (Grids 1 and 3: each WACC row moves the stable WACC by the same amount)
  Grid 4: value per share by moat spread
  Tornado: one input at a time from base, sorted by absolute $ impact
  Walk to Street assumptions (cumulative), with external estimates beside it
  Longer growth runway (A: fade years 11-10+n; B: Morningstar-style 14.8% to year 20)
  Discount-rate comparison (live CAPM formulas on sourced inputs)
Writes data/sensitivity_*.csv and regenerates the Sensitivity tab. Cross-checks two
grid cells through the workbook's own DCF formulas (Python evaluation only).

Usage:
    python scripts/sensitivity.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.formatting.formatting import ConditionalFormattingList
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, Side

from build_dcf import OVERRIDE, evaluate
from build_wacc import snapshot
from reverse import RESULTS, bisect, bridge, dcf, load_params, with_rates

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
DATA = ROOT / "data"
SHEET, INPUTS, DCF, REV, HIST = "Sensitivity", "Inputs", "DCF", "Reverse", "Historicals"
PCT, PCT2, PER_SHARE, USD_M, DELTA = "0.0%", "0.00%", "$0.00", "#,##0", '+$0.00;-$0.00;$0.00'
GREEN, YELLOW, RED = "63BE7B", "FFEB84", "F8696B"

MARGINS = [0.20, 0.225, 0.25, 0.275, 0.30]
TERMINAL_G = [0.02, 0.025, 0.03, 0.035, 0.04]
SBC = [("subtract (base)", 1), ("ignore", 0)]
MOATS = [0.0, 0.01, 0.02, 0.03, 0.05]

# Pre-lease preview from the 2026-10-20 brief: printed for comparison, never fails the run
PREVIEW = {"g1_base": 0.304, "moat": {0.0: 74.47, 0.01: 76.47, 0.02: 78.12, 0.03: 79.50, 0.05: 81.69},
           "walk": [78.12, 99.08, 104.48, 119.08, 135.04, 166.82],
           "runway": {"A, n = 5": 82.91, "A, n = 10": 88.07, "B (Morningstar-style)": 142.61,
                      "B at 8.8% WACC": 186.35}}

EXTERNAL = [  # (estimate, value per share, source / basis); comparison inputs, typed with sources
    ("Street consensus target", 175.89, "48 analysts, low $130, high $210, 0 Sells; MarketBeat, Oct 2026"),
    ("Morningstar fair value", 145.00, "Aug 2026; 2025 report: WACC 8.8%, CoE 9.0%, 3-stage to year 20, "
                                       "Stage II EBI growth 14.8%, mid-teens GAAP margin by 2029, tax 26.5%, wide moat"),
    ("Simply Wall St DCF", 113.77, "Oct 19 2026"),
]
DISCOUNT = [  # (source, risk-free, ERP, note); None = take from Inputs
    ("This model", None, None, "Inputs: 10Y Treasury (H.15) + Damodaran implied ERP"),
    ("Kroll inputs", 0.056, 0.050, "Kroll ERP 5.0% + spot 20-yr Treasury ~5.60% (H.15, Oct 13 2026)"),
    ("Fernandez 2025 survey", 0.041, 0.055, "Survey average ERP 5.5% + rf 4.1%"),
]
MORNINGSTAR_RATES = ("Morningstar (Shopify)", "9.0% cost of equity; 8.8% WACC (2025 equity report)")


def implied_growth(p):
    return bisect(lambda g: dcf(p, g)["vps"], p["price"], -0.5, 1.5)


# ------------------------------------------------------------ analyses

def tornado(p):
    base = dcf(p)["vps"]
    nonop = lambda h: {**p, "haircut": h, "nonop": bridge({**p, "haircut": h})}
    tests = [
        ("Risk-free rate", "5.21%", [("4.71%", with_rates(p, rf=0.0471)), ("5.71%", with_rates(p, rf=0.0571))]),
        ("Market risk premium", "4.14%", [("5.0%", with_rates(p, mrp=0.05)), ("5.5%", with_rates(p, mrp=0.055))]),
        ("Beta (high-growth)", "1.25", [("1.0", with_rates(p, beta=1.0)), ("1.5", with_rates(p, beta=1.5))]),
        ("GMV growth, year 1", "29%", [("25%", {**p, "g1": 0.25}), ("33%", {**p, "g1": 0.33})]),
        ("GMV growth, year 10", "7%", [("5%", {**p, "g10": 0.05}), ("9%", {**p, "g10": 0.09})]),
        ("Take-rate increase per year", "0.02 pt", [("0", {**p, "take_inc": 0.0}), ("0.03 pt", {**p, "take_inc": 0.0003})]),
        ("Terminal EBIT margin", "25%", [("20%", {**p, "margin10": 0.20}), ("30%", {**p, "margin10": 0.30})]),
        ("Terminal tax rate", "24%", [("26.5%", {**p, "tax10": 0.265})]),
        ("Year-1 tax rate", "19%", [("15%", {**p, "tax1": 0.15})]),
        ("Working capital % of revenue increase", "4%", [("2%", {**p, "wc": 0.02}), ("6%", {**p, "wc": 0.06})]),
        ("Loan book % of revenue increase", "20%", [("0%", {**p, "loans": 0.0}), ("15%", {**p, "loans": 0.15}),
                                                   ("25%", {**p, "loans": 0.25})]),
        ("Terminal growth", "3%", [("2.5%", {**p, "tg": 0.025}), ("3.5%", {**p, "tg": 0.035})]),
        ("Stable-period beta", "1.00", [("1.25", with_rates(p, beta_s=1.25))]),
        ("Moat spread", "2%", [("0%", {**p, "moat": 0.0}), ("3%", {**p, "moat": 0.03})]),
        ("SBC treatment", "cost", [("ignore", {**p, "flag": 0})]),
        ("Investment haircut", "20%", [("0%", nonop(0.0)), ("50%", nonop(0.5))]),
    ]
    rows = [(name, b, test, dcf(q)["vps"]) for name, b, ts in tests for test, q in ts]
    rows = [(name, b, test, v, v - base) for name, b, test, v in rows]
    return sorted(rows, key=lambda r: -abs(r[4])), base


def walk(p):
    steps = [("This model", {}), ("Treat SBC as free (SBC ignore)", {"flag": 0}),
             ("Ignore lending (loan book % = 0)", {"loans": 0.0}),
             ("9% WACC, stable 9% (≈ Simply Wall St)", {"wacc": 0.09, "stable_wacc": 0.09}),
             ("30% terminal EBIT margin (≈ Morningstar)", {"margin10": 0.30}),
             ("GMV growth 33% → 9% (≈ market / Street)", {"g1": 0.33, "g10": 0.09})]
    q, out = dict(p), []
    for label, ch in steps:
        q.update(ch)
        out.append((label, dcf(q)["vps"]))
    return out


def _stable_tv(p, rev_last, df_last):
    rev = rev_last * (1 + p["tg"])
    nopat = rev * p["margin10"] * (1 - p["tax10"])
    fcff = nopat * (1 - p["tg"] / (p["stable_wacc"] + p["moat"])) + (1 - p["flag"]) * p["sbc"] * rev
    return fcff / (p["stable_wacc"] - p["tg"]) * df_last


def runway_a(p, n):
    """Years 11..10+n: growth 7% -> terminal growth, discount rate high-growth -> stable WACC,
    reinvestment = NOPAT x g / ROIC_new with ROIC_new fading from year-10 ROIC on new capital to
    the stable ROIC; then the stable terminal value."""
    b = dcf(p)
    rev, df, pv = b["rev10"], b["df10"], b["pv"]
    roic10 = p["margin10"] * (1 - p["tax10"]) / (p["wc"] + p["loans"])
    roic_s = p["stable_wacc"] + p["moat"]
    for k in range(1, n + 1):
        g = p["g10"] + (p["tg"] - p["g10"]) * k / n
        r = p["wacc"] + (p["stable_wacc"] - p["wacc"]) * k / n
        roic = roic10 + (roic_s - roic10) * k / n
        rev *= 1 + g
        nopat = rev * p["margin10"] * (1 - p["tax10"])
        df /= 1 + r
        pv += (nopat * (1 - g / roic) + (1 - p["flag"]) * p["sbc"] * rev) * df
    return (pv + _stable_tv(p, rev, df) + p["nonop"]) / p["shares"], rev


def runway_b(p, g=0.148, years=10):
    """Years 11-20 at constant growth g, 25% margin, 24% tax, high-growth WACC, reinvestment as in
    years 1-10 (24% of the revenue increase); then the stable terminal value."""
    b = dcf(p)
    rev, df, pv = b["rev10"], b["df10"], b["pv"]
    for _ in range(years):
        prev = rev
        rev *= 1 + g
        nopat = rev * p["margin10"] * (1 - p["tax10"])
        fcff = (nopat + (p["da"] - p["capex"]) * rev - (p["wc"] + p["loans"]) * (rev - prev)
                + (1 - p["flag"]) * p["sbc"] * rev)
        df /= 1 + p["wacc"]
        pv += fcff * df
    return (pv + _stable_tv(p, rev, df) + p["nonop"]) / p["shares"], rev


def runways(p):
    return [("A, n = 5", "Fade 7% → 3% over years 11–15; ROIC and WACC fade to stable", 15, *runway_a(p, 5)),
            ("A, n = 10", "Fade 7% → 3% over years 11–20; ROIC and WACC fade to stable", 20, *runway_a(p, 10)),
            ("B (Morningstar-style)", "Years 11–20 at 14.8%, high-growth WACC, 24% reinvestment", 20, *runway_b(p)),
            ("B at 8.8% WACC", "As B, with 8.8% for the high-growth and stable periods", 20,
             *runway_b({**p, "wacc": 0.088, "stable_wacc": 0.088}))]


# ------------------------------------------------------------ main

def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    p, i_rows = load_params(wb)
    if wb[INPUTS][f"B{i_rows[OVERRIDE]}"].value is not None:
        sys.exit("The growth override is set; clear it so the base case is the growth fade.")
    d = wb[DCF]
    wb_vps = evaluate(wb, DCF, f"B{next(r for r in range(1, d.max_row + 1) if d.cell(r, 1).value == 'Value per share')}")
    base_vps = dcf(p)["vps"]
    assert abs(base_vps - wb_vps) <= 0.01, (base_vps, wb_vps)
    gap = p["wacc"] - p["stable_wacc"]
    waccs = sorted({0.08, 0.09, 0.10, 0.11, 0.12, p["wacc"]})
    print(f"Base case reproduced: ${base_vps:.4f} (workbook ${wb_vps:.4f}); price ${p['price']:.2f}; "
          f"WACC {p['wacc']:.3%}, stable {p['stable_wacc']:.3%} (gap {gap:.3%})")

    at = lambda w, extra: {**p, "wacc": w, "stable_wacc": w - gap, **extra}
    grid1 = [[implied_growth(at(w, {"margin10": m})) for m in MARGINS] for w in waccs]
    grid2 = [[implied_growth({**p, "tg": g, "flag": f}) for _, f in SBC] for g in TERMINAL_G]
    grid3 = [[dcf(at(w, {"margin10": m}))["vps"] for m in MARGINS] for w in waccs]
    grid4 = [dcf({**p, "moat": m})["vps"] for m in MOATS]
    torn, _ = tornado(p)
    wlk = walk(p)
    run = runways(p)

    write_csv("sensitivity_grid1.csv", "wacc \\ terminal_ebit_margin", waccs, MARGINS, grid1)
    write_csv("sensitivity_grid2.csv", "terminal_growth \\ sbc_treatment", TERMINAL_G, [s for s, _ in SBC], grid2)
    write_csv("sensitivity_grid3.csv", "wacc \\ terminal_ebit_margin (value per share, USD)", waccs, MARGINS, grid3)
    rows_csv("sensitivity_grid4.csv", ["moat_spread", "value_per_share"], [(m, round(v, 6)) for m, v in zip(MOATS, grid4)])
    rows_csv("sensitivity_tornado.csv", ["assumption", "base", "test", "value_per_share", "change_vs_base"],
             [(a, b, t, round(v, 6), round(dv, 6)) for a, b, t, v, dv in torn])
    rows_csv("sensitivity_walk.csv", ["step", "value_per_share"], [(s, round(v, 6)) for s, v in wlk])
    rows_csv("sensitivity_runway.csv", ["scenario", "description", "final_year", "value_per_share", "final_revenue_usd_m"],
             [(n, desc, y, round(v, 6), round(r, 3)) for n, desc, y, v, r in run])
    rates = [(s, p["rf"] if rf is None else rf, p["mrp"] if erp is None else erp, note) for s, rf, erp, note in DISCOUNT]
    beta_hg = (p["wacc"] - p["rf"]) / p["mrp"]
    rows_csv("sensitivity_discount_rates.csv", ["source", "risk_free", "erp", "coe_beta_stable", "coe_beta_high_growth", "note"],
             [(s, rf, e, round(rf + p["beta_s"] * e, 6), round(rf + beta_hg * e, 6), n) for s, rf, e, n in rates]
             + [(MORNINGSTAR_RATES[0], "", "", 0.09, 0.088, MORNINGSTAR_RATES[1])])

    report(p, waccs, grid1, grid2, grid3, grid4, torn, wlk, run, rates, beta_hg)
    write_tab(wb, p, i_rows, waccs, grid1, grid2, grid3, grid4, torn, wlk, run)
    wb.save(WORKBOOK)

    ok = cross_check(waccs, gap, p, i_rows, grid1, grid2)
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    changed = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print(f"\n== Tabs changed: {changed}")
    if not set(changed) <= {SHEET} or not ok:
        sys.exit("Validation failed")


def write_csv(name, corner, rows, cols, grid):
    with (DATA / name).open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([corner] + cols)
        for r, vals in zip(rows, grid):
            w.writerow([round(r, 6)] + [round(v, 6) for v in vals])


def rows_csv(name, header, rows):
    with (DATA / name).open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def report(p, waccs, grid1, grid2, grid3, grid4, torn, wlk, run, rates, beta_hg):
    def show(title, rows, cols, grid, fmt):
        print(f"\n== {title}")
        print("  " + f"{'':>10}" + "".join(f"{c if isinstance(c, str) else format(c, '.1%'):>14}" for c in cols))
        for r, vals in zip(rows, grid):
            print("  " + f"{format(r, '.3%'):>10}" + "".join(f"{format(v, fmt):>14}" for v in vals))
    show("Grid 1: implied constant GMV growth (WACC ↓ / terminal EBIT margin →)", waccs, MARGINS, grid1, ".2%")
    show("Grid 2: implied constant GMV growth (terminal growth ↓ / SBC →)", TERMINAL_G, [s for s, _ in SBC], grid2, ".2%")
    show("Grid 3: value per share (WACC ↓ / terminal EBIT margin →)", waccs, MARGINS, grid3, ",.2f")
    g1b = grid1[waccs.index(p["wacc"])][2]
    print(f"\n  Grid 1 base {g1b:.2%} (pre-lease preview ≈ {PREVIEW['g1_base']:.1%})")
    print("\n== Grid 4: value per share by moat spread (pre-lease preview in brackets)")
    for m, v in zip(MOATS, grid4):
        print(f"  {m:5.0%}  ${v:7.2f}  (${PREVIEW['moat'][m]:.2f})")
    print("\n== Tornado (sorted by absolute change)")
    for a, b, t, v, dv in torn:
        print(f"  {a:40} {b:>8} → {t:<8} ${v:7.2f}  {dv:+7.2f}")
    print("\n== Walk to Street assumptions (pre-lease preview in brackets)")
    for (s, v), pv in zip(wlk, PREVIEW["walk"]):
        print(f"  {s:46} ${v:7.2f}  (${pv:.2f})")
    print("\n== Longer growth runway (pre-lease preview in brackets)")
    for n, desc, y, v, r in run:
        print(f"  {n:22} ${v:7.2f}  year-{y} revenue ${r / 1e3:,.1f}B  (${PREVIEW['runway'][n]:.2f})")
    print("\n== Discount rates (cost of equity at stable beta / high-growth beta)")
    for s, rf, e, note in rates:
        print(f"  {s:22} rf {rf:.2%} ERP {e:.2%} → {rf + p['beta_s'] * e:.2%} / {rf + beta_hg * e:.3%}")


def write_tab(wb, p, i_rows, waccs, grid1, grid2, grid3, grid4, torn, wlk, run):
    ws = wb[SHEET]
    for row in ws.iter_rows(min_row=5, max_row=max(ws.max_row, 120)):
        for c in row:
            c.value, c.comment, c.border = None, None, Border()
            c.style = "Normal"
    ws.conditional_formatting = ConditionalFormattingList()
    ws.cell(4, 1).value = "Grid"
    note = f"Generated by scripts/sensitivity.py, {date.today().isoformat()}; re-run if inputs change"
    thick = Side(style="thick")
    base_border = Border(left=thick, right=thick, top=thick, bottom=thick)
    rev = wb[REV]
    r_rows = {rev.cell(r, 1).value: r for r in range(1, rev.max_row + 1) if rev.cell(r, 1).value}
    hist = wb[HIST]
    h_header = next(r for r in range(1, hist.max_row + 1) if hist.cell(r, 1).value == "Item")
    h_cols = {hist.cell(h_header, c).value: c for c in range(1, hist.max_column + 1)}
    h_rows = {hist.cell(r, 1).value: r for r in range(h_header + 1, hist.max_row + 1) if hist.cell(r, 1).value}
    I = lambda label: f"{INPUTS}!$B${i_rows[label]}"
    nxt = [5]

    def section(title):
        for col in range(1, 14):
            ws.cell(nxt[0], col).style = "Section"
        ws.cell(nxt[0], 1).value = title
        nxt[0] += 1

    def foot():
        ws.cell(nxt[0], 1, note).font = Font(italic=True, color="808080")
        nxt[0] += 2

    def heat(rng, low_is_good):
        lo, hi = (GREEN, RED) if low_is_good else (RED, GREEN)
        ws.conditional_formatting.add(rng, ColorScaleRule(start_type="min", start_color=lo, mid_type="percentile",
                                                          mid_value=50, mid_color=YELLOW, end_type="max", end_color=hi))

    def grid(corner, rows, cols, values, fmt_r, fmt_c, fmt_v, base, low_is_good, first_col=2, label_col=1):
        top = nxt[0]
        ws.cell(top, label_col, corner).style = "Header"
        for k, col_val in enumerate(cols):
            c = ws.cell(top, first_col + k, col_val)
            c.style = "Header"
            if fmt_c:
                c.number_format = fmt_c
            c.alignment = Alignment(horizontal="center")
        for j, (rv, vals) in enumerate(zip(rows, values)):
            r = top + 1 + j
            rc = ws.cell(r, label_col, rv)
            rc.number_format, rc.font, rc.alignment = fmt_r, Font(bold=True), Alignment(horizontal="right")
            for k, v in enumerate(vals):
                c = ws.cell(r, first_col + k)
                c.value, c.style = (v, "Formula") if isinstance(v, str) else (float(v), "Input")
                c.number_format = fmt_v
                if base == (j, k):
                    c.border = base_border
        heat(f"{ws.cell(top + 1, first_col).coordinate}:{ws.cell(top + len(rows), first_col + len(cols) - 1).coordinate}",
             low_is_good)
        return top

    def table(headers, rows, fmts, styles, col0=1):
        top = nxt[0]
        for k, h in enumerate(headers):
            c = ws.cell(top, col0 + k, h)
            c.style = "Header"
        for j, vals in enumerate(rows):
            for k, v in enumerate(vals):
                c = ws.cell(top + 1 + j, col0 + k, v)
                if v is not None:
                    c.style = styles[k]
                    if fmts[k]:
                        c.number_format = fmts[k]
        return top

    i_base = waccs.index(p["wacc"])
    price = f"${p['price']:.2f}"

    section(f"Grid 1: implied constant GMV growth (all 10 years) for value per share = {price}")
    grid("WACC ↓ / Terminal EBIT margin →", waccs, MARGINS, grid1, PCT2, PCT, PCT, (i_base, 2), True)
    nxt[0] += 1 + len(waccs)
    ws.cell(nxt[0], 1, note + ". Each WACC row moves the stable WACC by the same amount.").font = \
        Font(italic=True, color="808080")
    nxt[0] += 1
    ws.cell(nxt[0], 1, "For comparison (live)").font = Font(bold=True)
    for k, lab in enumerate(["Actual GMV growth, FY2025", "Actual GMV growth, H1 2026",
                             "Base-case-equivalent constant growth (b)"]):
        ws.cell(nxt[0], 2 + 2 * k, lab).alignment = Alignment(wrap_text=True)
    nxt[0] += 1
    links = [f"={HIST}!{hist.cell(h_rows['GMV growth %'], h_cols['FY2025']).coordinate}",
             f"={HIST}!{hist.cell(h_rows['GMV growth %'], h_cols['H1 2026']).coordinate}",
             f"={REV}!B{r_rows[RESULTS[1][0]]}"]
    for k, f in enumerate(links):
        c = ws.cell(nxt[0], 2 + 2 * k, f)
        c.style, c.number_format = "Link", PCT
    nxt[0] += 2

    section("Grid 2: implied constant GMV growth, terminal growth × SBC treatment")
    grid("Terminal growth ↓ / SBC treatment →", TERMINAL_G, [s for s, _ in SBC], grid2, PCT, None, PCT,
         (TERMINAL_G.index(0.03), 0), True)
    nxt[0] += 1 + len(TERMINAL_G)
    foot()

    section("Grid 3: value per share (forward DCF, base growth fade)")
    top = grid("WACC ↓ / Terminal EBIT margin →", waccs, MARGINS, grid3, PCT2, PCT, PER_SHARE, (i_base, 2), False)
    first = 2 + len(MARGINS) + 1
    upside = [[f"={ws.cell(top + 1 + j, 2 + k).coordinate}/{I('Share price')}-1" for k in range(len(MARGINS))]
              for j in range(len(waccs))]
    nxt[0] = top
    grid("Upside / (downside) vs price →", waccs, MARGINS, upside, PCT2, PCT, PCT, (i_base, 2), False,
         first_col=first + 1, label_col=first)
    nxt[0] = top + 1 + len(waccs)
    foot()

    section("Grid 4: value per share by moat spread over the stable WACC")
    grid("Moat spread →", ["Value per share"], MOATS, [grid4], "@", PCT, PER_SHARE, (0, MOATS.index(0.02)), False)
    nxt[0] += 2
    foot()

    section("Single-assumption impact (tornado): one input at a time from base, sorted by absolute impact")
    top = table(["Assumption", "Base", "Test", "Value per share", "Change vs base"],
                [list(r) for r in torn], [None, None, None, PER_SHARE, DELTA], ["Normal", "Normal", "Normal", "Input", "Input"])
    ws.conditional_formatting.add(f"E{top + 1}:E{top + len(torn)}",
                                  ColorScaleRule(start_type="min", start_color=RED, mid_type="num", mid_value=0,
                                                 mid_color="FFFFFF", end_type="max", end_color=GREEN))
    nxt[0] = top + 1 + len(torn)
    foot()

    section("Walk to Street assumptions (cumulative) and external estimates")
    top = table(["Step (cumulative)", "Value per share", "Change"],
                [[s, v, (v - wlk[k - 1][1]) if k else None] for k, (s, v) in enumerate(wlk)],
                [None, PER_SHARE, DELTA], ["Normal", "Input", "Input"])
    ext_top = top
    hdr = ["External estimate", "Value per share", "Source / basis"]
    for k, h in enumerate(hdr):
        ws.cell(ext_top, 8 + k, h).style = "Header"
    for j, (name, v, src) in enumerate(EXTERNAL + [("Current share price", f"={I('Share price')}", "Inputs")]):
        ws.cell(ext_top + 1 + j, 8, name)
        c = ws.cell(ext_top + 1 + j, 9, v)
        c.style, c.number_format = ("Link" if isinstance(v, str) else "Input"), PER_SHARE
        ws.cell(ext_top + 1 + j, 10, src)
    nxt[0] = top + 1 + max(len(wlk), len(EXTERNAL) + 1)
    foot()

    section("Longer growth runway (beyond the 10-year forecast; Python-only scenarios)")
    top = table(["Scenario", "Value per share", "Final year", "Final-year revenue (USD m)", "Description"],
                [[n, v, y, r, desc] for n, desc, y, v, r in run], [None, PER_SHARE, "0", USD_M, None],
                ["Normal", "Input", "Input", "Input", "Normal"])
    nxt[0] = top + 1 + len(run)
    foot()

    section("Discount-rate comparison (cost of equity = risk-free + beta × ERP; live)")
    top = table(["Source", "Risk-free", "ERP", "Market rate (stable β)", "At high-growth β", "Notes"], [], [], [])
    beta_hg = f"(({I('WACC')}-{I('Risk-free rate')})/{I('Market risk premium')})"
    for j, (src, rf, erp, notes) in enumerate(DISCOUNT):
        r = top + 1 + j
        ws.cell(r, 1, src)
        rf_c = ws.cell(r, 2, f"={I('Risk-free rate')}" if rf is None else rf)
        erp_c = ws.cell(r, 3, f"={I('Market risk premium')}" if erp is None else erp)
        for c, v in ((rf_c, rf), (erp_c, erp)):
            c.style, c.number_format = ("Link" if v is None else "Input"), PCT2
        for col, beta in ((4, I("Stable-period beta")), (5, beta_hg)):
            c = ws.cell(r, col, f"=B{r}+{beta}*C{r}")
            c.style, c.number_format = "Formula", PCT2
        ws.cell(r, 6, notes)
    r = top + 1 + len(DISCOUNT)
    ws.cell(r, 1, MORNINGSTAR_RATES[0])
    for col, v in ((4, 0.09), (5, 0.088)):
        c = ws.cell(r, col, v)
        c.style, c.number_format = "Input", PCT2
    ws.cell(r, 6, MORNINGSTAR_RATES[1] + " (8.8% shown under high-growth β is their WACC)")
    nxt[0] = r + 1
    ws.cell(nxt[0], 1, "Rates are typed inputs with sources; the cost of equity uses this model's betas.").font = \
        Font(italic=True, color="808080")
    ws.column_dimensions["H"].width = 30
    ws.freeze_panes = "A5"


def cross_check(waccs, gap, p, i_rows, grid1, grid2):
    """Two non-base cells through the workbook's own DCF formulas (Python evaluation only)."""
    wb = load_workbook(WORKBOOK)
    d = wb[DCF]
    vps_cell = f"B{next(r for r in range(1, d.max_row + 1) if d.cell(r, 1).value == 'Value per share')}"
    I = lambda label: (INPUTS, f"B{i_rows[label]}")
    print("\n== Cross-check through the workbook's DCF formulas")
    rev = wb[REV]
    a = next(rev.cell(r, 2).value for r in range(1, rev.max_row + 1) if rev.cell(r, 1).value == RESULTS[0][0])
    g_base = grid1[waccs.index(p["wacc"])][2]
    ok = abs(g_base - a) <= 0.001
    print(f"  {'OK  ' if ok else 'FAIL'} Grid 1 base {g_base:.4%} vs Reverse (a) {a:.4%}")
    cases = [
        ("Grid 1: WACC 8.0% (stable 8.0% − gap), margin 20.0%",
         {I("WACC"): 0.08, I("Stable-period WACC"): 0.08 - gap, I("Terminal EBIT margin (year 10)"): 0.20,
          I(OVERRIDE): grid1[waccs.index(0.08)][0]}),
        ("Grid 2: terminal growth 2.0%, SBC ignore",
         {I("Terminal growth rate"): 0.02, I("SBC treatment"): "ignore", I(OVERRIDE): grid2[0][1]}),
    ]
    for name, ov in cases:
        v = evaluate(wb, DCF, vps_cell, ov)
        good = abs(v - p["price"]) <= 0.01
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {name}: override {ov[I(OVERRIDE)]:.4%} -> value per share ${v:.4f}")
    vps = evaluate(wb, DCF, vps_cell)
    blank = wb[INPUTS][I(OVERRIDE)[1]].value is None
    ok &= blank and abs(vps - dcf(p)["vps"]) <= 0.005
    print(f"  Restored: Inputs!{I(OVERRIDE)[1]} blank = {blank}; value per share ${vps:.2f}")
    return ok


if __name__ == "__main__":
    main()
