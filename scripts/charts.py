"""Charts for the memo, saved to charts/ (PNG, 200 dpi) and placed on the Reality Check tab.

  1. revenue_path.png            historical revenue, the base-case path and the path the price implies
  2. implied_growth_heatmap.png  implied constant GMV growth by WACC x terminal EBIT margin (Grid 1)
  3. gmv_share.png               Shopify GMV as a share of global e-commerce (eMarketer bars, Forrester markers)
  4. scenarios_vs_price.png      bear / base / bull value per share vs the price and the Street mean
Data: data/historicals.csv, data/sensitivity_grid1.csv, data/reality_check_results.csv,
data/scenarios.csv, the Reverse tab (implied growth) and the DCF replica (scripts/reverse.py).
Run after scripts/reality_check.py. Replaces any earlier chart images on the tab.

Usage:
    python scripts/charts.py
"""

import csv
import sys
import textwrap
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from openpyxl.drawing.image import Image  # noqa: E402

from build_wacc import snapshot  # noqa: E402
from reverse import dcf, load_params  # noqa: E402
from sensitivity import EXTERNAL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
DATA, OUT = ROOT / "data", ROOT / "charts"
SHEET = "Reality Check"
DPI = 200
INK, GREY, LIGHT = "#1F2937", "#6B7280", "#E5E7EB"
BLUE, ORANGE, RED, GREEN = "#1F3864", "#C2410C", "#B91C1C", "#15803D"
STREET = next(v for n, v, _ in EXTERNAL if n.startswith("Street"))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GREY, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left"})


def read(name):
    with (DATA / name).open() as fh:
        return list(csv.reader(fh))


def source_line(fig, text):
    fig.text(0.01, 0.012, "\n".join(textwrap.wrap(text, 135)), fontsize=7.5, color=GREY, ha="left", va="bottom")


def finish(fig, ax, source, name):
    ax.yaxis.grid(True, color=LIGHT, linewidth=0.8)
    ax.set_axisbelow(True)
    source_line(fig, source)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    path = OUT / name
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def revenue_path(p, implied_g):
    hist = {(r[0], r[1]): float(r[3]) for r in read("historicals.csv")[1:] if r[0] == "Total revenue" and r[3]}
    fy = [(int(per[2:]) + 1.0, hist[("Total revenue", per)]) for per in ("FY2021", "FY2022", "FY2023", "FY2024", "FY2025")]
    ttm = hist[("Total revenue", "FY2025")] + hist[("Total revenue", "H1 2026")] - hist[("Total revenue", "H1 2025")]
    x_hist = [x for x, _ in fy] + [2026.5]
    y_hist = [v for _, v in fy] + [ttm]
    base, implied = dcf(p)["rev_path"], dcf(p, implied_g)["rev_path"]
    x_fc = [2026.5 + t for t in range(len(base))]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    b = lambda vs: [v / 1e3 for v in vs]
    ax.plot(x_hist, b(y_hist), color=INK, linewidth=2.2, marker="o", markersize=4, label="Reported (FY2021–FY2025, TTM Jun-26)")
    ax.plot(x_fc, b(base), color=BLUE, linewidth=2, label="Base case (GMV growth 29% → 7%)")
    ax.plot(x_fc, b(implied), color=ORANGE, linewidth=2, linestyle="--",
            label=f"Price-implied ({implied_g:.1%} constant GMV growth)")
    for ys, col in ((base, BLUE), (implied, ORANGE)):
        ax.annotate(f"${ys[-1] / 1e3:,.0f}B", (x_fc[-1], ys[-1] / 1e3), xytext=(6, 0), textcoords="offset points",
                    va="center", color=col, fontweight="bold")
    ax.set_title("Revenue: reported, base case and what the $172.50 price implies")
    ax.set_xlabel("Period end (reported: fiscal years to Dec 31, TTM to Jun 30 2026; forecast: years to Jun 30)")
    ax.set_xticks(range(2022, 2038, 2))
    ax.set_ylabel("Revenue (USD billions)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}B"))
    ax.set_xlim(2021.6, 2038.0)
    ax.legend(frameon=False, loc="upper left")
    return finish(fig, ax, "Source: SEC filings (10-K, 40-F, 10-Q) via XBRL; forecast from this model (scripts/reverse.py). "
                           "Price-implied path: constant GMV growth that sets value per share = $172.50.", "revenue_path.png")


def heatmap(p):
    g = read("sensitivity_grid1.csv")
    margins = [float(c) for c in g[0][1:]]
    waccs = [float(r[0]) for r in g[1:]]
    z = [[float(v) for v in r[1:]] for r in g[1:]]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    im = ax.imshow(z, cmap="RdYlGn_r", aspect="auto")
    lo, hi = min(min(r) for r in z), max(max(r) for r in z)
    for i, row in enumerate(z):
        for j, v in enumerate(row):
            base = abs(waccs[i] - p["wacc"]) < 1e-9 and abs(margins[j] - p["margin10"]) < 1e-9
            extreme = not 0.15 < (v - lo) / (hi - lo) < 0.85
            ax.text(j, i, f"{v:.1%}", ha="center", va="center", fontsize=10, color="white" if extreme else INK,
                    fontweight="bold" if base else "normal")
            if base:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=INK, linewidth=2.5))
    ax.set_xticks(range(len(margins)), [f"{m:.1%}" for m in margins])
    pct2 = lambda w: f"{Decimal(repr(w * 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)}%"  # as Excel displays it
    ax.set_yticks(range(len(waccs)), [pct2(w) + (" (base)" if abs(w - p["wacc"]) < 1e-9 else "") for w in waccs])
    ax.set_xlabel("Terminal EBIT margin (year 10)")
    ax.set_ylabel("WACC, years 1–10 (stable WACC moves in step)")
    ax.set_title("GMV growth needed every year for 10 years to justify $172.50")
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, format=PercentFormatter(1.0, decimals=0))
    cb.outline.set_visible(False)
    cb.set_label("Implied constant GMV growth")
    source_line(fig, "Source: this model, Sensitivity tab Grid 1 (scripts/sensitivity.py). Reference: GMV growth "
                     "FY2025 29.5%, H1 2026 33.0%. Box = base case.")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    path = OUT / "implied_growth_heatmap.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def gmv_share():
    res = {r[0]: (float(r[2]), float(r[3])) for r in read("reality_check_results.csv")[1:]}
    cases = [("Today\n(TTM Jun-26)", "today", INK), ("Bear", "bear", GREY), ("Base", "base", BLUE),
             ("Bull", "bull", GREY), ("Market-implied\n(price)", "implied", ORANGE)]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    xs = range(len(cases))
    bars = ax.bar(xs, [res[k][0] for _, k, _ in cases], color=[c for *_, c in cases], width=0.6,
                  label="Share of eMarketer market")
    ax.scatter(xs, [res[k][1] for _, k, _ in cases], marker="D", color="white", edgecolor=INK, zorder=3, s=36,
               label="Share of Forrester market")
    for bar, (_, k, _) in zip(bars, cases):
        ax.text(bar.get_x() + bar.get_width() / 2, max(res[k]) + 0.018, f"{res[k][0]:.1%}", ha="center", va="bottom",
                fontweight="bold", color=INK)
    ax.set_xticks(list(xs), [lab for lab, *_ in cases])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("Shopify GMV ÷ global retail e-commerce")
    ax.set_title("Shopify's share of global e-commerce: today and in year 10 (2035–36)")
    ax.set_ylim(0, max(max(v) for v in res.values() if v) * 1.15)
    ax.legend(frameon=False, loc="upper left")
    return finish(fig, ax, "Source: eMarketer Forecast Feb 2025 (via shopify.com), extended at 7.1%/yr; Forrester May 2024, "
                           "extended at 8.9%/yr; Shopify GMV (10-K/10-Q); this model. GMV includes offline and B2B, so shares are "
                           "upper bounds.", "gmv_share.png")


def scenarios(p):
    sc = {r[0]: r[1:] for r in read("scenarios.csv")}
    vals = [float(v) for v in sc["Value per share"]]
    weighted = float(sc["Probability-weighted value per share"][0])
    labels = ["Bear", "Base", "Bull", "Probability-\nweighted"]
    ys = vals + [weighted]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(range(4), ys, color=[GREY, BLUE, GREY, "#9CA3AF"], width=0.6)
    for bar, v in zip(bars, ys):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 3, f"${v:,.2f}", ha="center", va="bottom", fontweight="bold", color=INK)
    ax.axhline(p["price"], color=RED, linewidth=1.8)
    ax.text(3.45, p["price"] - 3, f"Share price ${p['price']:.2f}", color=RED, ha="right", va="top", fontweight="bold")
    ax.axhline(STREET, color=INK, linewidth=1.2, linestyle="--")
    ax.text(3.45, STREET + 3, f"Street mean target ${STREET:.2f}", color=INK, ha="right", va="bottom")
    ax.set_xticks(range(4), labels)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_ylabel("Value per share (USD)")
    ax.set_ylim(0, STREET * 1.18)
    ax.set_title("Scenario values vs the share price")
    return finish(fig, ax, "Source: this model, Scenarios tab (scripts/scenarios.py; weights 25/50/25). Price: NASDAQ close "
                           "Oct 14 2026. Street mean: 48 analysts, MarketBeat, Oct 2026.", "scenarios_vs_price.png")


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")
    OUT.mkdir(exist_ok=True)
    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    p, _ = load_params(wb)
    rev = wb["Reverse"]
    g = next(rev.cell(r, 2).value for r in range(1, rev.max_row + 1)
             if rev.cell(r, 1).value == "(a) Implied constant GMV growth (10 years)")
    paths = [revenue_path(p, g), heatmap(p), gmv_share(), scenarios(p)]

    ws = wb[SHEET]
    ws._images = []
    for r in range(1, ws.max_row + 1):  # drop the previous run's heading so re-runs stay put
        if str(ws.cell(r, 1).value or "").startswith("Charts (scripts/charts.py"):
            for c in range(1, 18):
                ws.cell(r, c).value = None
                ws.cell(r, c).style = "Normal"
    last = max(r for r in range(1, ws.max_row + 1) if any(ws.cell(r, c).value is not None for c in range(1, 18)))
    top = last + 3
    ws.cell(top - 1, 1, f"Charts (scripts/charts.py, {date.today().isoformat()}; PNGs in charts/)").style = "Section"
    for k, path in enumerate(paths):
        img = Image(str(path))
        scale = 620 / img.width
        img.width, img.height = 620, img.height * scale
        anchor = f"{'A' if k % 2 == 0 else 'G'}{top + (k // 2) * 19}"
        ws.add_image(img, anchor)
    wb.save(WORKBOOK)
    after = snapshot(load_workbook(WORKBOOK))
    tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print("Charts:", *[str(x.relative_to(ROOT)) for x in paths], sep="\n  ")
    print(f"Inserted {len(paths)} images on {SHEET!r} from row {top}; tabs changed: {tabs}; "
          f"images on tab after reload: {len(load_workbook(WORKBOOK)[SHEET]._images)}")


if __name__ == "__main__":
    main()
