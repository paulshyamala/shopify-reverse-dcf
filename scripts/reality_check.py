"""Reality check: what the price implies for Shopify's share of global e-commerce.

Writes data/reality_check.csv (sourced market forecasts, filled in and extended to 2036
at each source's own CAGR) and regenerates the tables on the Reality Check tab:
  A. market inputs (reported points blue, filled-in / extended years black formulas)
  B. Shopify today: TTM GMV (link to Inputs) as a share of each source's market today
  C. implied year 10: GMV at the price-implied constant growth (link to Reverse) and the
     bear / base / bull year-10 GMV (links to Scenarios), as shares of the year-10 market
  D. take-rate check: GMV needed for the price-implied year-10 revenue at three take rates
  E. notes (GMV definition vs retail e-commerce; FY2025 context)
"Today" = average of 2025 and 2026 (TTM ends mid-2026); "year 10" = average of 2035 and 2036.
Market values are stored in USD m (the model's unit) and displayed in trillions.
Charts are added below the tables by scripts/charts.py (existing images are kept).

Stops without saving if a share differs from the expected value by more than 1 point.

Usage:
    python scripts/reality_check.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from build_dcf import evaluate
from build_wacc import snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SRC_CSV = ROOT / "data" / "reality_check.csv"
OUT_CSV = ROOT / "data" / "reality_check_results.csv"
SHEET, INPUTS, REV, SCEN = "Reality Check", "Inputs", "Reverse", "Scenarios"
YEARS = list(range(2023, 2037))
TODAY, YEAR10 = (2025, 2026), (2035, 2036)
TN, USD_M, PCT, PCT2 = '0.000,," tn"', "#,##0", "0.0%", "0.00%"
TRILLION = 1e6  # USD m per USD trillion (for the CSV only; the tab stores USD m)

SOURCES = {
    "eMarketer": {
        "label": "eMarketer, worldwide retail e-commerce",
        "reported": {2024: 6.007, 2025: 6.419, 2026: 6.880, 2027: 7.375, 2028: 7.886},
        "cagr_from": (2025, 2028),  # CAGR computed from the source's own points
        "note": "EMARKETER Forecast, Feb 2025, as cited at shopify.com/blog/global-ecommerce-sales; "
                "extended after 2028 at its 2025–28 CAGR",
    },
    "Forrester": {
        "label": "Forrester, global online retail",
        "reported": {2023: 4.4, 2028: 6.8},
        "cagr": 0.089,  # stated in the release
        "note": "Forrester press release, May 30 2024 (Business Wire): $4.4T (2023) → $6.8T (2028), 8.9% CAGR; "
                "2024–27 filled in and post-2028 extended at 8.9%",
    },
}
STEP_TEST = 0.001  # +0.10 percentage point of take rate per year (test iii)
NOTES = [
    "Shopify GMV includes offline (POS) and B2B sales, which retail e-commerce forecasts exclude, "
    "so these shares are overstated (upper bounds).",
    "FY2025 context: GMV $378B, +29% (10-K KPI table); B2B GMV +96% (full year); Q4 offline GMV +29%; "
    "Q4 Europe GMV +45% (35% constant currency).",
    "B2B, offline and Europe growth are from coverage of Shopify's Q4 2025 results (Digital Commerce 360, earnings-call "
    "transcript, Zacks); not stated in the 10-K or the Feb 11 2026 release.",
    "Forrester's rounded endpoints imply 9.1% a year (4.4 → 6.8); the stated 8.9% is used, so 2027 → 2028 steps up "
    "slightly to the reported 6.8T.",
]
EXPECTED = {  # brief, 2026-10-20; tolerance 1 point
    ("today", "eMarketer"): 0.065, ("today", "Forrester"): 0.079, ("implied", "eMarketer"): 0.47,
    ("base", "eMarketer"): 0.17, ("flat", "eMarketer"): 0.50, ("step", "eMarketer"): 0.38,
}


def series():
    """Each source's yearly values (USD tn) and how each point was obtained."""
    out = {}
    for name, s in SOURCES.items():
        rep = s["reported"]
        if "cagr_from" in s:
            a, b = s["cagr_from"]
            cagr = (rep[b] / rep[a]) ** (1 / (b - a)) - 1
        else:
            cagr = s["cagr"]
        vals, kinds = {}, {}
        first = min(rep)
        for y in YEARS:
            if y in rep:
                vals[y], kinds[y] = rep[y], "reported"
            elif y > first:
                vals[y], kinds[y] = vals[y - 1] * (1 + cagr), ("extended" if y > max(rep) else "filled in")
        out[name] = (vals, kinds, cagr)
    return out


def write_csv(ser):
    with SRC_CSV.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["source", "year", "value_usd_tn", "type", "cagr_used", "source_note"])
        for name, (vals, kinds, cagr) in ser.items():
            for y in YEARS:
                if y in vals:
                    w.writerow([name, y, round(vals[y], 6), kinds[y], round(cagr, 6), SOURCES[name]["note"]])


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")
    ser = series()
    write_csv(ser)

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws, inp, rev, scn = wb[SHEET], wb[INPUTS], wb[REV], wb[SCEN]
    rows = lambda sh: {sh.cell(r, 1).value: r for r in range(1, sh.max_row + 1) if sh.cell(r, 1).value}
    I, R, SC = rows(inp), rows(rev), rows(scn)
    link_i = lambda lab: f"={INPUTS}!$B${I[lab]}"
    for row in ws.iter_rows(min_row=5, max_row=max(ws.max_row, 60), max_col=20):
        for c in row:
            c.value, c.comment = None, None
            c.style = "Normal"
    ws.cell(4, 1).value = "Item"
    col = {y: get_column_letter(2 + k) for k, y in enumerate(YEARS)}      # 2023 -> B ... 2036 -> O
    cagr_col, note_col = get_column_letter(2 + len(YEARS)), get_column_letter(3 + len(YEARS))
    nxt = [5]

    def section(title):
        for c in range(1, 4 + len(YEARS)):
            ws.cell(nxt[0], c).style = "Section"
        ws.cell(nxt[0], 1).value = title
        nxt[0] += 1

    def header(labels, start=1):
        for k, lab in enumerate(labels):
            c = ws.cell(nxt[0], start + k, lab)
            c.style = "Header"
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        nxt[0] += 1

    def put(r, c, value, style, fmt=None):
        cell = ws.cell(r, c, value)
        cell.style = style
        if fmt:
            cell.number_format = fmt
        return cell

    def note(text, r=None):
        r = nxt[0] if r is None else r
        ws.cell(r, 1, text).font = Font(italic=True, color="808080")
        if r == nxt[0]:
            nxt[0] += 1

    # ---- A. market inputs
    section("A. Global e-commerce market (USD trillion; reported = blue input, filled-in / extended = black formula)")
    hdr_row = nxt[0]
    header(["Source"] + YEARS + ["CAGR used", "Source / date"])
    src_row = {}
    for name, s in SOURCES.items():
        r = nxt[0]
        src_row[name] = r
        ws.cell(r, 1, s["label"])
        vals, kinds, _ = ser[name]
        rep = s["reported"]
        for y in YEARS:
            c = ws.cell(r, 2 + YEARS.index(y))
            if y in rep:
                put(r, c.column, rep[y] * TRILLION, "Input", TN)
            elif y in vals:
                put(r, c.column, f"={col[y - 1]}{r}*(1+${cagr_col}${r})", "Formula", TN)
        if "cagr_from" in s:
            a, b = s["cagr_from"]
            put(r, 2 + len(YEARS), f"=({col[b]}{r}/{col[a]}{r})^(1/({col[b]}${hdr_row}-{col[a]}${hdr_row}))-1",
                "Formula", PCT2)
        else:
            put(r, 2 + len(YEARS), s["cagr"], "Input", PCT2)
        ws.cell(r, 3 + len(YEARS), s["note"])
        nxt[0] += 1
    note(f"Today = average of {TODAY[0]} and {TODAY[1]} (TTM ends Jun 30 2026); year 10 = average of "
         f"{YEAR10[0]} and {YEAR10[1]} (forecast year 10 ends Jun 30 2036).")
    nxt[0] += 1
    mkt = lambda name, yrs: f"AVERAGE({col[yrs[0]]}{src_row[name]}:{col[yrs[1]]}{src_row[name]})"

    # ---- B. Shopify today
    section("B. Shopify today")
    header(["Item", "eMarketer basis", "Forrester basis", "Notes"])
    r_today, r_y10, r_gmv, r_share = nxt[0], nxt[0] + 1, nxt[0] + 2, nxt[0] + 3
    ws.cell(r_today, 1, f"Market today (average {TODAY[0]}–{str(TODAY[1])[2:]})")
    ws.cell(r_y10, 1, f"Market year 10 (average {YEAR10[0]}–{str(YEAR10[1])[2:]})")
    ws.cell(r_gmv, 1, "Shopify TTM GMV (Inputs)")
    ws.cell(r_share, 1, "Shopify share of market today")
    for k, name in enumerate(SOURCES):
        c = 2 + k
        put(r_today, c, f"={mkt(name, TODAY)}", "Formula", TN)
        put(r_y10, c, f"={mkt(name, YEAR10)}", "Formula", TN)
        put(r_gmv, c, link_i("TTM GMV"), "Link", USD_M)
        put(r_share, c, f"={get_column_letter(c)}{r_gmv}/{get_column_letter(c)}{r_today}", "Formula", PCT)
    ws.cell(r_gmv, 4, "TTM to Jun 30 2026, USD m")
    nxt[0] = r_share + 2

    # ---- C. implied year 10
    section("C. Implied year 10: Shopify GMV as a share of the year-10 market")
    r_g, r_n = nxt[0], nxt[0] + 1
    ws.cell(r_g, 1, "Price-implied constant GMV growth (Reverse)")
    put(r_g, 2, f"={REV}!$B${R['(a) Implied constant GMV growth (10 years)']}", "Link", PCT2)
    ws.cell(r_g, 4, "Reverse DCF result (a), scripts/reverse.py")
    ws.cell(r_n, 1, "Forecast years (Inputs)")
    put(r_n, 2, link_i("Forecast years"), "Link", "0")
    nxt[0] = r_n + 1
    header(["Case", "Year-10 GMV (USD m)", "Share, eMarketer", "Share, Forrester", "Notes"])
    gmv10 = f"Year-10 GMV"
    cases = [("Market-implied (constant growth)", f"=B{r_gmv}*(1+B{r_g})^B{r_n}", "Formula", "TTM GMV × (1 + implied growth)^years"),
             ("Bear scenario", f"={SCEN}!$B${SC[gmv10]}", "Link", "Scenarios tab"),
             ("Base case", f"={SCEN}!$C${SC[gmv10]}", "Link", "Scenarios tab (= DCF base case)"),
             ("Bull scenario", f"={SCEN}!$D${SC[gmv10]}", "Link", "Scenarios tab")]
    case_rows = {}
    for label, formula, style, why in cases:
        r = nxt[0]
        case_rows[label] = r
        ws.cell(r, 1, label)
        put(r, 2, formula, style, USD_M)
        put(r, 3, f"=B{r}/B{r_y10}", "Formula", PCT)
        put(r, 4, f"=B{r}/C{r_y10}", "Formula", PCT)
        ws.cell(r, 5, why)
        nxt[0] += 1
    nxt[0] += 1

    # ---- D. take-rate check
    section("D. Take-rate check: GMV needed for the price-implied year-10 revenue")
    r_rev, r_step = nxt[0], nxt[0] + 1
    ws.cell(r_rev, 1, "Price-implied year-10 revenue (Reverse)")
    put(r_rev, 2, f"={REV}!$B${R['(a) Year-10 revenue']}", "Link", USD_M)
    ws.cell(r_rev, 4, "USD m; Reverse DCF at the implied constant growth, model take-rate path")
    ws.cell(r_step, 1, "Take-rate step for test (iii)")
    put(r_step, 2, STEP_TEST, "Input", PCT2)
    ws.cell(r_step, 4, "Test assumption: +0.10 percentage point per year")
    nxt[0] = r_step + 1
    header(["Take-rate case", "Year-10 take rate", "GMV needed (USD m)", "Share, eMarketer", "Share, Forrester"])
    takes = [("(i) Flat at the TTM take rate", link_i("TTM take rate"), "Link"),
             ("(ii) Model take-rate path", f"={INPUTS}!$B${I['TTM take rate']}+{INPUTS}!$B${I['Take rate increase per year']}*B{r_n}", "Formula"),
             ("(iii) +0.10 pt per year", f"={INPUTS}!$B${I['TTM take rate']}+B{r_step}*B{r_n}", "Formula")]
    take_rows = {}
    for label, formula, style in takes:
        r = nxt[0]
        take_rows[label] = r
        ws.cell(r, 1, label)
        put(r, 2, formula, style, PCT2)
        put(r, 3, f"=B{r_rev}/B{r}", "Formula", USD_M)
        put(r, 4, f"=C{r}/B{r_y10}", "Formula", PCT)
        put(r, 5, f"=C{r}/C{r_y10}", "Formula", PCT)
        nxt[0] += 1
    nxt[0] += 1

    # ---- E. notes
    section("E. Notes")
    for text in NOTES:
        ws.cell(nxt[0], 1, text).alignment = Alignment(wrap_text=False)
        nxt[0] += 1
    note(f"Generated by scripts/reality_check.py, {date.today().isoformat()}; re-run if inputs change. "
         "Charts below: scripts/charts.py.")
    ws.freeze_panes = "B5"

    # ---- evaluate, check, save
    ev = lambda coord: evaluate(wb, SHEET, coord)
    res = {("today", "eMarketer"): ev(f"B{r_share}"), ("today", "Forrester"): ev(f"C{r_share}")}
    for key, label in (("implied", "Market-implied (constant growth)"), ("bear", "Bear scenario"),
                       ("base", "Base case"), ("bull", "Bull scenario")):
        res[(key, "eMarketer")], res[(key, "Forrester")] = ev(f"C{case_rows[label]}"), ev(f"D{case_rows[label]}")
    for key, label in (("flat", "(i) Flat at the TTM take rate"), ("path", "(ii) Model take-rate path"),
                       ("step", "(iii) +0.10 pt per year")):
        res[(key, "eMarketer")], res[(key, "Forrester")] = ev(f"D{take_rows[label]}"), ev(f"E{take_rows[label]}")
    gmv = {"today": ev(f"B{r_gmv}"), **{k: ev(f"B{case_rows[l]}") for k, l in
                                        (("implied", "Market-implied (constant growth)"), ("bear", "Bear scenario"),
                                         ("base", "Base case"), ("bull", "Bull scenario"))},
           **{k: ev(f"C{take_rows[l]}") for k, l in (("flat", "(i) Flat at the TTM take rate"),
                                                    ("path", "(ii) Model take-rate path"), ("step", "(iii) +0.10 pt per year"))}}
    markets = {"today": (ev(f"B{r_today}"), ev(f"C{r_today}")), "year10": (ev(f"B{r_y10}"), ev(f"C{r_y10}"))}
    print(f"Markets (USD tn): today eMarketer {markets['today'][0] / TRILLION:.3f} / Forrester {markets['today'][1] / TRILLION:.3f}; "
          f"year 10 {markets['year10'][0] / TRILLION:.3f} / {markets['year10'][1] / TRILLION:.3f}")
    print(f"  {'case':10} {'GMV (USD tn)':>13} {'eMarketer':>10} {'Forrester':>10}  expected")
    bad = []
    for key in ("today", "implied", "bear", "base", "bull", "flat", "path", "step"):
        exp = EXPECTED.get((key, "eMarketer")), EXPECTED.get((key, "Forrester"))
        for e, src in zip(exp, ("eMarketer", "Forrester")):
            if e is not None and abs(res[(key, src)] - e) > 0.01:
                bad.append((key, src, res[(key, src)], e))
        hint = " / ".join(f"{x:.1%}" if x is not None else "–" for x in exp)
        print(f"  {key:10} {gmv[key] / TRILLION:13.3f} {res[(key, 'eMarketer')]:10.1%} {res[(key, 'Forrester')]:10.1%}  {hint}")
    if bad:
        sys.exit(f"STOP: results differ from expected by more than 1 point: {bad} (workbook not saved)")

    with OUT_CSV.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case", "gmv_usd_m", "share_emarketer", "share_forrester"])
        for key in ("today", "implied", "bear", "base", "bull", "flat", "path", "step"):
            w.writerow([key, round(gmv[key], 3), round(res[(key, "eMarketer")], 6), round(res[(key, "Forrester")], 6)])
    wb.save(WORKBOOK)
    after = snapshot(load_workbook(WORKBOOK))
    tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print(f"Saved. Tabs changed: {tabs}; wrote {SRC_CSV.relative_to(ROOT)} and {OUT_CSV.relative_to(ROOT)}")
    if not set(tabs) <= {SHEET}:
        sys.exit("Something outside the Reality Check tab changed")


if __name__ == "__main__":
    main()
