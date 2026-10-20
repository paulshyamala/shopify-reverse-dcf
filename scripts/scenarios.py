"""Bull / base / bear scenarios on the Scenarios tab.

Reuses load_params() and the DCF replica from scripts/reverse.py. Each scenario
overrides only the seven inputs below; everything else stays at base. Base values
are live links to Inputs; Bear and Bull are blue inputs on the Scenarios tab. On
the first run they are seeded from DEFAULTS; on later runs they (and the weights)
are read back from the tab, so edit them there and re-run.
Writes data/scenarios.csv and the Scenarios tab (inputs, script outputs, a live
check against the DCF tab, and a live probability-weighted value).

Usage:
    python scripts/scenarios.py
"""

import csv
from copy import copy
import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from build_dcf import OVERRIDE, evaluate
from build_wacc import snapshot
from reverse import dcf, load_params, with_rates

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
OUT_CSV = ROOT / "data" / "scenarios.csv"
SHEET, INPUTS, DCF = "Scenarios", "Inputs", "DCF"
PCT, PCT2, USD_M, MULT, PER_SHARE = "0.0%", "0.00%", "#,##0", '0.0"x"', "$0.00"
SCEN = ["Bear", "Base", "Bull"]

# (row label, replica key, Inputs label, format, bear, bull, rationale)
INPUT_ROWS = [
    ("GMV growth, year 1", "g1", "GMV growth, year 1", PCT, 0.25, 0.33,
     "Bear: fast slowdown (Amazon, marketplaces, AI shopping agents). Bull: H1 2026's 33% pace holds longer."),
    ("GMV growth, year 10", "g10", "GMV growth, year 10", PCT, 0.05, 0.09, "As above"),
    ("Take rate increase per year", "take_inc", "Take rate increase per year", PCT2, 0.0, 0.0003,
     "Bear: payments pricing pressure. Bull: more payments, ads and B2B."),
    ("Terminal EBIT margin (year 10)", "margin10", "Terminal EBIT margin (year 10)", PCT, 0.20, 0.30,
     "Bear ≈ PayPal FY2025 GAAP 18.3%. Bull: mature-software scale."),
    ("Loan book % of revenue increase", "loans", "Loan book % of revenue increase", PCT, 0.22, 0.18,
     "Bear: lending needs more capital. Bull: more capital-efficient."),
    ("WACC", "wacc", "WACC", PCT2, 0.115, 0.095,
     "Bear sits between the industry-beta (10.4%) and adjusted-beta (13.8%) cost of equity. Bull: lower risk premium."),
    ("Terminal growth rate", "tg", "Terminal growth rate", PCT, 0.025, 0.035,
     "All below ~4% long-run nominal GDP (Fed SEP)."),
    ("Moat spread over stable WACC", "moat", "Moat spread over stable WACC", PCT, 0.0, 0.03,
     "Bear: no excess return after year 10 (ROIC = WACC). Bull: upper end of Damodaran's 2–3% for moat firms."),
]
STABLE_NOTE = ("Stable period: beta 1.00 in all scenarios (stable WACC = risk-free + 1.0 × MRP); "
               "the WACC row is the high-growth (years 1–10) rate.")
WEIGHTS = (0.25, 0.50, 0.25)
OUTPUTS = [  # (label, key, format)
    ("Value per share", "vps", PER_SHARE),
    ("Upside / (downside) vs price", "upside", PCT),
    ("Enterprise value", "ev", USD_M),
    ("Equity value", "equity", USD_M),
    ("PV of terminal value % of EV", "tv_pct", PCT),
    ("Year-10 GMV", "gmv10", USD_M),
    ("Year-10 revenue", "rev10", USD_M),
    ("Year-10 FCFF", "fcff10", USD_M),
    ("TV / year-10 EBIT", "tv_ebit", MULT),
]
PREVIEW = {"Bear": 45.29, "Base": 78.12, "Bull": 129.18, "weighted": 82.68}  # 2026-10-20 brief, pre-lease; info only
WEIGHTS_LABEL, WEIGHTED_LABEL, CHECK_LABEL = "Weights", "Probability-weighted value per share", \
    "Check: base scenario − DCF value per share"


def outputs(p):
    o = dcf(p)
    pv_tv = o["ev"] - o["pv"]
    tv = pv_tv / o["df10"]
    return {"vps": o["vps"], "upside": o["vps"] / p["price"] - 1, "ev": o["ev"],
            "equity": o["vps"] * p["shares"], "tv_pct": pv_tv / o["ev"], "gmv10": o["gmv10"],
            "rev10": o["rev10"], "fcff10": o["fcff10"], "tv_ebit": tv / (o["rev10"] * o["margin10"])}


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    p, i_rows = load_params(wb)
    if wb[INPUTS][f"B{i_rows[OVERRIDE]}"].value is not None:
        sys.exit("The growth override is set; clear it so the base case is the growth fade.")
    base_vps = dcf(p)["vps"]
    d = wb[DCF]
    wb_vps = evaluate(wb, DCF, f"B{next(r for r in range(1, d.max_row + 1) if d.cell(r, 1).value == 'Value per share')}")
    assert abs(base_vps - wb_vps) <= 0.01, (base_vps, wb_vps)
    assert abs(with_rates(p, beta_s=1.0)["stable_wacc"] - p["stable_wacc"]) < 1e-12, "stable beta is not 1.00 on Inputs"
    print(f"Base case reproduced: ${base_vps:.4f} (workbook ${wb_vps:.4f}); stable WACC {p['stable_wacc']:.3%} in all scenarios")

    ws = wb[SHEET]
    labels = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value}
    # Bear/Bull and weights: from the tab if it's already laid out, else the defaults
    bear = {k: float(ws.cell(labels[lab], 2).value if lab in labels else b) for lab, k, _, _, b, _, _ in INPUT_ROWS}
    bull = {k: float(ws.cell(labels[lab], 4).value if lab in labels else u) for lab, k, _, _, _, u, _ in INPUT_ROWS}
    weights = tuple(float(ws.cell(labels[WEIGHTS_LABEL], c).value) for c in (2, 3, 4)) \
        if WEIGHTS_LABEL in labels else WEIGHTS
    params = {"Bear": {**p, **bear}, "Base": p, "Bull": {**p, **bull}}
    res = {s: outputs(params[s]) for s in SCEN}
    weighted = sum(w * res[s]["vps"] for w, s in zip(weights, SCEN))

    print(f"\n  {'':32}" + "".join(f"{s:>14}" for s in SCEN))
    for lab, k, _, fmt, *_ in INPUT_ROWS:
        print(f"  {lab:32}" + "".join(f"{params[s][k]:>14.3%}" for s in SCEN))
    for lab, k, fmt in OUTPUTS:
        f = (lambda v: f"${v:,.2f}") if fmt == PER_SHARE else (lambda v: f"{v:.1%}") if fmt == PCT else \
            (lambda v: f"{v:.1f}x") if fmt == MULT else (lambda v: f"{v:,.0f}")
        print(f"  {lab:32}" + "".join(f"{f(res[s][k]):>14}" for s in SCEN))
    print(f"  {'Weighted value per share':32}{'$' + format(weighted, ',.2f'):>14}  (weights {weights})")

    ok = abs(res["Base"]["vps"] - base_vps) < 1e-9
    print("\n== Compared with the pre-lease preview (informational)")
    for s in SCEN:
        print(f"  {s:5} ${res[s]['vps']:.2f}  (preview ${PREVIEW[s]:.2f}; {res[s]['vps'] - PREVIEW[s]:+.2f})")
    print(f"  weighted ${weighted:.2f}  (preview ${PREVIEW['weighted']:.2f}; {weighted - PREVIEW['weighted']:+.2f})")

    with OUT_CSV.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["item"] + [s.lower() for s in SCEN])
        for lab, k, *_ in INPUT_ROWS:
            w.writerow([lab] + [round(params[s][k], 6) for s in SCEN])
        for lab, k, _ in OUTPUTS:
            w.writerow([lab] + [round(res[s][k], 6) for s in SCEN])
        w.writerow(["Weights"] + list(weights))
        w.writerow([WEIGHTED_LABEL, round(weighted, 6), "", ""])

    write_tab(wb, i_rows, bear, bull, weights, res)
    wb.save(WORKBOOK)

    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    s = wb[SHEET]
    lab = {s.cell(r, 1).value: r for r in range(1, s.max_row + 1) if s.cell(r, 1).value}
    check = evaluate(wb, SHEET, f"B{lab[CHECK_LABEL]}")
    live_weighted = evaluate(wb, SHEET, f"B{lab[WEIGHTED_LABEL]}")
    print(f"\n== Workbook: live check (base − DCF) = {check:.10f}; live weighted value ${live_weighted:.2f}; "
          f"Inputs!B{i_rows[OVERRIDE]} blank = {wb[INPUTS][f'B{i_rows[OVERRIDE]}'].value is None}; tabs changed: {tabs}")
    ok &= abs(check) < 1e-6 and abs(live_weighted - weighted) < 1e-6 and set(tabs) <= {SHEET}
    if not ok:
        sys.exit("Validation failed")


def write_tab(wb, i_rows, bear, bull, weights, res):
    ws = wb[SHEET]
    for row in ws.iter_rows(min_row=4, max_row=max(ws.max_row, 40)):
        for c in row:
            c.value, c.comment = None, None
            c.style = "Normal"
    for col, text in enumerate(["Item"] + SCEN + ["Rationale / notes"], start=1):
        ws.cell(4, col, text).style = "Header"
    ws.column_dimensions["E"].width = 100
    note = f"Generated by scripts/scenarios.py, {date.today().isoformat()}; re-run if inputs change"
    nxt = [5]

    def section(title):
        for col in range(1, 6):
            ws.cell(nxt[0], col).style = "Section"
        ws.cell(nxt[0], 1).value = title
        nxt[0] += 1

    section("Scenario inputs (everything else at base case)")
    for lab, k, i_label, fmt, *_, why in INPUT_ROWS:
        r = nxt[0]
        ws.cell(r, 1, lab)
        for col, val, style in ((2, bear[k], "Input"), (3, f"={INPUTS}!$B${i_rows[i_label]}", "Link"),
                                (4, bull[k], "Input")):
            c = ws.cell(r, col, val)
            c.style, c.number_format = style, fmt
        ws.cell(r, 5, why)
        nxt[0] += 1
    ws.cell(nxt[0], 1, STABLE_NOTE).font = Font(italic=True, color="808080")
    nxt[0] += 2

    section("Outputs (scripts/scenarios.py)")
    vps_row = nxt[0]
    highlight = PatternFill("solid", start_color="DDEBF7", end_color="DDEBF7")
    for lab, k, fmt in OUTPUTS:
        r = nxt[0]
        ws.cell(r, 1, lab)
        for col, s in zip((2, 3, 4), SCEN):
            c = ws.cell(r, col, float(res[s][k]))
            c.style, c.number_format = "Input", fmt
        nxt[0] += 1
    price = ws.cell(vps_row, 5, f"={INPUTS}!$B${i_rows['Share price']}")
    price.style, price.number_format = "Link", '"Current share price "$0.00'
    price.alignment = Alignment(horizontal="left")
    for col in range(1, 5):
        c = ws.cell(vps_row, col)
        c.fill, c.font = highlight, Font(bold=True, color=copy(c.font.color) if c.font.color else None)
    ws.cell(nxt[0], 1, note).font = Font(italic=True, color="808080")
    nxt[0] += 1
    d = wb[DCF]
    dcf_vps = next(r for r in range(1, d.max_row + 1) if d.cell(r, 1).value == "Value per share")
    r = nxt[0]
    ws.cell(r, 1, CHECK_LABEL)
    c = ws.cell(r, 2, f"={ws.cell(vps_row, 3).coordinate}-{DCF}!$B${dcf_vps}")
    c.style, c.number_format = "Formula", PER_SHARE
    ws.cell(r, 5, "Live: should be $0.00 (re-run scripts/scenarios.py if not)")
    nxt[0] += 2

    section("Probability-weighted value (illustrative)")
    r = nxt[0]
    ws.cell(r, 1, WEIGHTS_LABEL)
    for col, w in zip((2, 3, 4), weights):
        c = ws.cell(r, col, w)
        c.style, c.number_format = "Input", "0%"
    ws.cell(r, 5, "Illustrative weights, bear / base / bull")
    w_row = r
    r += 1
    ws.cell(r, 1, WEIGHTED_LABEL).font = Font(bold=True)
    terms = "+".join(f"{ws.cell(vps_row, col).coordinate}*{ws.cell(w_row, col).coordinate}" for col in (2, 3, 4))
    c = ws.cell(r, 2, f"={terms}")
    c.style, c.number_format = "Formula", PER_SHARE
    c.font = Font(bold=True)
    c.border = Border(*(Side(style="medium"),) * 4)
    ws.cell(r, 5, "Live: scenario values × weights")
    ws.freeze_panes = "B5"


if __name__ == "__main__":
    main()
