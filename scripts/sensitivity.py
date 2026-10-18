"""Sensitivity grids for the reverse and forward DCF.

Reuses the DCF replica and the bisection solver from scripts/reverse.py and reads
every assumption from the workbook. Asserts the base case first. Then computes:
  Grid 1: implied constant GMV growth (value = price), WACC x terminal EBIT margin
  Grid 2: implied constant GMV growth, terminal growth x SBC treatment
  Grid 3: value per share (forward DCF, base growth fade), WACC x terminal EBIT margin
Writes data/sensitivity_grid{1,2,3}.csv and regenerates the Sensitivity tab
(script-output values, heatmaps, base-cell borders, a live comparison row).
Cross-checks two non-base cells against the workbook's own DCF formulas (inputs
changed only inside the Python evaluation; nothing is saved to Inputs).

Usage:
    python scripts/sensitivity.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.cell_range import CellRange
from openpyxl.formatting.formatting import ConditionalFormattingList

from build_dcf import OVERRIDE, evaluate
from build_wacc import snapshot
from reverse import RESULTS, bisect, dcf, load_params

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
DATA = ROOT / "data"
SHEET, INPUTS, DCF, REV, HIST = "Sensitivity", "Inputs", "DCF", "Reverse", "Historicals"
PCT, PCT2, PER_SHARE = "0.0%", "0.00%", "$0.00"
GREEN, YELLOW, RED = "63BE7B", "FFEB84", "F8696B"

MARGINS = [0.20, 0.225, 0.25, 0.275, 0.30]
TERMINAL_G = [0.02, 0.025, 0.03, 0.035, 0.04]
SBC = [("subtract (base)", 1), ("ignore", 0)]

EXPECTED = {  # preview from the brief, 0.05 pp tolerance (grid 3: $0.01)
    "g1_base": 0.291,
    "g1_row8": [0.250, 0.233, 0.219, 0.206, 0.194],
    "g1_row12": [0.370, 0.350, 0.333, 0.318, 0.305],
    "g2": {0.03: (0.291, 0.260), 0.02: (0.305, 0.274), 0.04: (0.275, 0.244)},
    "g3_base": 84.10,
}


def implied_growth(p):
    return bisect(lambda g: dcf(p, g)["vps"], p["price"], -0.5, 1.5)


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
    assert abs(base_vps - 84.10) <= 0.01, base_vps
    waccs = sorted({0.08, 0.09, 0.10, 0.11, 0.12, p["wacc"]})
    print(f"Base case reproduced: ${base_vps:.4f}; price ${p['price']:.2f}; WACC {p['wacc']:.3%}")

    grid1 = [[implied_growth({**p, "wacc": w, "margin10": m}) for m in MARGINS] for w in waccs]
    grid2 = [[implied_growth({**p, "tg": g, "flag": f}) for _, f in SBC] for g in TERMINAL_G]
    grid3 = [[dcf({**p, "wacc": w, "margin10": m})["vps"] for m in MARGINS] for w in waccs]

    write_csv("sensitivity_grid1.csv", "wacc \\ terminal_ebit_margin", waccs, MARGINS, grid1)
    write_csv("sensitivity_grid2.csv", "terminal_growth \\ sbc_treatment", TERMINAL_G, [s for s, _ in SBC], grid2)
    write_csv("sensitivity_grid3.csv", "wacc \\ terminal_ebit_margin (value per share, USD)", waccs, MARGINS, grid3)

    ok = check_expected(waccs, p, grid1, grid2, grid3)
    write_tab(wb, p, waccs, grid1, grid2, grid3)
    wb.save(WORKBOOK)

    ok &= cross_check(waccs, p, i_rows, grid1, grid2)
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    changed = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print(f"\n== Tabs changed: {changed}")
    if changed != [SHEET] or not ok:
        sys.exit("Validation failed")


def write_csv(name, corner, rows, cols, grid):
    with (DATA / name).open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([corner] + cols)
        for r, vals in zip(rows, grid):
            w.writerow([round(r, 6)] + [round(v, 6) for v in vals])


def show(title, rows, cols, grid, fmt_r, fmt_v, base):
    print(f"\n== {title}")
    print("  " + f"{'':>10}" + "".join(f"{c if isinstance(c, str) else format(c, fmt_r):>16}" for c in cols))
    for r, vals in zip(rows, grid):
        print("  " + f"{format(r, '.3%'):>10}" + "".join(
            f"{(format(v, fmt_v) + (' *' if (r, c) == base else '')):>16}" for c, v in zip(cols, vals)))


def check_expected(waccs, p, grid1, grid2, grid3):
    show("Grid 1: implied constant GMV growth (WACC ↓ / terminal EBIT margin →)", waccs, MARGINS, grid1,
         ".1%", ".2%", (p["wacc"], 0.25))
    show("Grid 2: implied constant GMV growth (terminal growth ↓ / SBC →)", TERMINAL_G, [s for s, _ in SBC],
         grid2, ".1%", ".2%", (0.03, "subtract (base)"))
    show("Grid 3: value per share, base growth fade (WACC ↓ / terminal EBIT margin →)", waccs, MARGINS,
         [[v for v in row] for row in grid3], ".1%", ",.2f", (p["wacc"], 0.25))
    i = lambda w: waccs.index(w)
    checks = [("Grid 1 base", grid1[i(p["wacc"])][2], EXPECTED["g1_base"])]
    checks += [(f"Grid 1 row 8%, margin {m:.1%}", grid1[i(0.08)][k], e) for k, (m, e) in enumerate(zip(MARGINS, EXPECTED["g1_row8"]))]
    checks += [(f"Grid 1 row 12%, margin {m:.1%}", grid1[i(0.12)][k], e) for k, (m, e) in enumerate(zip(MARGINS, EXPECTED["g1_row12"]))]
    for g, (es, ei) in EXPECTED["g2"].items():
        row = grid2[TERMINAL_G.index(g)]
        checks += [(f"Grid 2 tg {g:.1%} subtract", row[0], es), (f"Grid 2 tg {g:.1%} ignore", row[1], ei)]
    print("\n== Checks vs preview (0.05 pp; grid 3 $0.01)")
    ok = True
    for name, got, exp in checks:
        good = abs(got - exp) <= 0.0005
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {name:32} {got:.2%} vs {exp:.1%}")
    g3 = grid3[i(p["wacc"])][2]
    good = abs(g3 - EXPECTED["g3_base"]) <= 0.01
    ok &= good
    print(f"  {'OK  ' if good else 'FAIL'} {'Grid 3 base':32} ${g3:.2f} vs ${EXPECTED['g3_base']:.2f}")
    return ok


def write_tab(wb, p, waccs, grid1, grid2, grid3):
    ws = wb[SHEET]
    for row in ws.iter_rows(min_row=5, max_row=max(ws.max_row, 60)):
        for c in row:
            c.value, c.comment = None, None
            c.style = "Normal"
    ws.conditional_formatting = ConditionalFormattingList()
    ws.cell(4, 1).value = "Grid"
    note = f"Generated by scripts/sensitivity.py, {date.today().isoformat()}; re-run if inputs change"
    thick = Side(style="thick")
    base_border = Border(left=thick, right=thick, top=thick, bottom=thick)
    hdr = lambda c: setattr(c, "style", "Header")
    rev = wb[REV]
    r_rows = {rev.cell(r, 1).value: r for r in range(1, rev.max_row + 1) if rev.cell(r, 1).value}
    hist = wb[HIST]
    h_header = next(r for r in range(1, hist.max_row + 1) if hist.cell(r, 1).value == "Item")
    h_cols = {hist.cell(h_header, c).value: c for c in range(1, hist.max_column + 1)}
    h_rows = {hist.cell(r, 1).value: r for r in range(h_header + 1, hist.max_row + 1) if hist.cell(r, 1).value}
    nxt = [5]

    def section(title):
        for col in range(1, 14):
            ws.cell(nxt[0], col).style = "Section"
        ws.cell(nxt[0], 1).value = title
        nxt[0] += 1

    def grid(corner, rows, cols, values, fmt_r, fmt_c, fmt_v, base, low_is_good, first_col=2, label_col=1):
        top = nxt[0]
        c = ws.cell(top, label_col, corner)
        hdr(c)
        for k, col_val in enumerate(cols):
            c = ws.cell(top, first_col + k, col_val)
            hdr(c)
            if fmt_c:
                c.number_format = fmt_c
            c.alignment = Alignment(horizontal="center")
        for j, (rv, vals) in enumerate(zip(rows, values)):
            r = top + 1 + j
            rc = ws.cell(r, label_col, rv)
            rc.number_format, rc.font, rc.alignment = fmt_r, Font(bold=True), Alignment(horizontal="right")
            for k, v in enumerate(vals):
                c = ws.cell(r, first_col + k)
                if isinstance(v, str):
                    c.value, c.style = v, "Formula"
                else:
                    c.value, c.style = float(v), "Input"
                c.number_format = fmt_v
                if base == (j, k):
                    c.border = base_border
        rng = f"{ws.cell(top + 1, first_col).coordinate}:{ws.cell(top + len(rows), first_col + len(cols) - 1).coordinate}"
        lo, hi = (GREEN, RED) if low_is_good else (RED, GREEN)
        ws.conditional_formatting.add(rng, ColorScaleRule(start_type="min", start_color=lo, mid_type="percentile",
                                                          mid_value=50, mid_color=YELLOW, end_type="max", end_color=hi))
        return top, rng

    i_base = waccs.index(p["wacc"])
    price = f"${p['price']:.2f}"

    section(f"Grid 1: implied constant GMV growth (all 10 years) for value per share = {price}")
    grid("WACC ↓ / Terminal EBIT margin →", waccs, MARGINS, grid1, PCT2, PCT, PCT, (i_base, 2), low_is_good=True)
    nxt[0] += 1 + len(waccs)
    ws.cell(nxt[0], 1, note).font = Font(italic=True, color="808080")
    nxt[0] += 1
    labels = ["Actual GMV growth, FY2025", "Actual GMV growth, H1 2026", "Base-case-equivalent constant growth (b)"]
    ws.cell(nxt[0], 1, "For comparison (live)").font = Font(bold=True)
    for k, lab in enumerate(labels):
        c = ws.cell(nxt[0], 2 + 2 * k, lab)
        c.alignment = Alignment(wrap_text=True)
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
         (TERMINAL_G.index(0.03), 0), low_is_good=True)
    nxt[0] += 1 + len(TERMINAL_G)
    ws.cell(nxt[0], 1, note).font = Font(italic=True, color="808080")
    nxt[0] += 2

    section("Grid 3: value per share (forward DCF, base growth fade)")
    top, rng = grid("WACC ↓ / Terminal EBIT margin →", waccs, MARGINS, grid3, PCT2, PCT, PER_SHARE,
                    (i_base, 2), low_is_good=False)
    # Upside / (downside) vs price: live formulas on the values to the left
    first = 2 + len(MARGINS) + 1
    price_ref = f"{INPUTS}!$B${next(r for r in range(1, wb[INPUTS].max_row + 1) if wb[INPUTS].cell(r, 1).value == 'Share price')}"
    upside = [[f"={ws.cell(top + 1 + j, 2 + k).coordinate}/{price_ref}-1" for k in range(len(MARGINS))]
              for j in range(len(waccs))]
    nxt[0] = top
    grid("Upside / (downside) vs price →", waccs, MARGINS, upside, PCT2, PCT, PCT, (i_base, 2), low_is_good=False,
         first_col=first + 1, label_col=first)
    nxt[0] = top + 1 + len(waccs)
    ws.cell(nxt[0], 1, note).font = Font(italic=True, color="808080")
    ws.column_dimensions["H"].width = 30
    ws.freeze_panes = "A5"


def cross_check(waccs, p, i_rows, grid1, grid2):
    """Two non-base cells, through the workbook's own DCF formulas (Python evaluation only)."""
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
        ("Grid 1: WACC 8.0%, margin 20.0%", {I("WACC"): 0.08, I("Terminal EBIT margin (year 10)"): 0.20,
                                             I(OVERRIDE): grid1[waccs.index(0.08)][0]}),
        ("Grid 2: terminal growth 2.0%, SBC ignore", {I("Terminal growth rate"): 0.02, I("SBC treatment"): "ignore",
                                                      I(OVERRIDE): grid2[0][1]}),
    ]
    for name, ov in cases:
        v = evaluate(wb, DCF, vps_cell, ov)
        good = abs(v - p["price"]) <= 0.01
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {name}: override {ov[I(OVERRIDE)]:.4%} -> value per share ${v:.4f}")
    vps = evaluate(wb, DCF, vps_cell)
    blank = wb[INPUTS][I(OVERRIDE)[1]].value is None
    ok &= blank and abs(vps - 84.10) <= 0.005
    print(f"  Restored: Inputs!{I(OVERRIDE)[1]} blank = {blank}; value per share ${vps:.2f}")
    return ok


if __name__ == "__main__":
    main()
