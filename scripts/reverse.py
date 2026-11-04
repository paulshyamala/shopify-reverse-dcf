"""Reverse DCF: what the share price implies, solved in Python.

Reads every assumption from the workbook (Inputs, found by label), replicates
the DCF tab exactly, and first asserts it reproduces the workbook's base case.
Then solves by bisection (tolerance $0.001/share):
  (a) implied constant GMV growth (all 10 years) so value per share = price
  (b) the constant growth that gives the base-case value (like-for-like with the fade)
  (c) implied terminal (year-10) EBIT margin, base growth fade, so value = price
  (d) implied year-1 GMV growth, still fading linearly to year-10 growth, so value = price
and writes the results into the Reverse tab's Results block (blue values).
Also checks the workbook itself: with (a) in the override cell, the DCF formulas
give value per share = price (evaluated in Python; the override is not saved).

Usage:
    python scripts/reverse.py
"""

import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from build_dcf import OVERRIDE, evaluate
from build_reverse import RESULTS
from build_wacc import snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
INPUTS, DCF, REV = "Inputs", "DCF", "Reverse"
TOL = 0.001  # $/share

LABELS = {
    "rev0": "Starting revenue (TTM)", "gmv0": "TTM GMV", "take0": "TTM take rate", "margin0": "TTM EBIT margin",
    "g1": "GMV growth, year 1", "g10": "GMV growth, year 10", "take_inc": "Take rate increase per year",
    "margin10": "Terminal EBIT margin (year 10)", "tax1": "Tax rate, year 1", "tax10": "Tax rate, year 10",
    "da": "D&A % of revenue", "capex": "Capex % of revenue", "wc": "Working capital % of revenue increase",
    "loans": "Loan book % of revenue increase", "flag": "SBC deduction flag", "sbc": "SBC % of revenue (forecast)",
    "tg": "Terminal growth rate", "years": "Forecast years", "wacc": "WACC", "nonop": "Net non-operating assets",
    "shares": "Diluted shares outstanding", "price": "Share price", "override": OVERRIDE,
    # stable period (Damodaran Rules 3 & 4) and the inputs behind the discount rates
    "stable_wacc": "Stable-period WACC", "moat": "Moat spread over stable WACC", "beta_s": "Stable-period beta",
    "rf": "Risk-free rate", "mrp": "Market risk premium",
    # equity bridge components (for haircut / lease tests)
    "cash_sec": "Cash & securities (100%)", "eq_inv": "Equity & other investments",
    "flexport": "Flexport (equity method)", "debt": "Debt", "haircut": "Haircut on investments",
    "leases": "Lease liabilities",
}
OPTIONAL = {"leases": 0.0}  # labels that may not exist yet -> default


def dcf(p, growth=None):
    """The DCF tab in Python. growth: None = fade; float = constant; callable t -> g.

    Years 1-10 at the high-growth WACC. Year 11 (Damodaran Rules 3 & 4): NOPAT at the
    terminal margin and year-10 tax, reinvestment = NOPAT x g / stable ROIC (stable ROIC
    = stable WACC + moat), TV = FCFF11 / (stable WACC - g), discounted at the year-10 factor.
    """
    n = int(p["years"])
    gmv, rev, out = p["gmv0"], p["rev0"], {"pv": 0.0, "gmv_path": [p["gmv0"]], "rev_path": [p["rev0"]]}
    for t in range(1, n + 1):
        if callable(growth):
            g = growth(t)
        elif growth is not None:
            g = growth
        else:
            g = p["g1"] + (p["g10"] - p["g1"]) * (t - 1) / (n - 1)
        prev_rev = rev
        gmv = gmv * (1 + g)
        rev = gmv * (p["take0"] + p["take_inc"] * t)
        margin = p["margin0"] + (p["margin10"] - p["margin0"]) * t / n
        tax = p["tax1"] + (p["tax10"] - p["tax1"]) * (t - 1) / (n - 1)
        fcff = (rev * margin * (1 - tax) + p["da"] * rev - p["capex"] * rev
                - (p["wc"] + p["loans"]) * (rev - prev_rev) + (1 - p["flag"]) * p["sbc"] * rev)
        df = 1 / (1 + p["wacc"]) ** t
        out["pv"] += fcff * df
        out["gmv_path"].append(gmv)
        out["rev_path"].append(rev)
    out.update(gmv10=gmv, rev10=rev, fcff10=fcff, df10=df, margin10=margin, tax10=tax,
               nopat10=rev * margin * (1 - tax))
    rev11 = rev * (1 + p["tg"])
    nopat11 = rev11 * margin * (1 - tax)
    stable_roic = p["stable_wacc"] + p["moat"]
    reinv_rate = p["tg"] / stable_roic
    fcff11 = nopat11 * (1 - reinv_rate) + (1 - p["flag"]) * p["sbc"] * rev11
    tv = fcff11 / (p["stable_wacc"] - p["tg"])
    out.update(rev11=rev11, nopat11=nopat11, fcff11=fcff11, tv=tv, pv_tv=tv * df,
               stable_roic=stable_roic, reinv_rate=reinv_rate)
    out["ev"] = out["pv"] + tv * df
    out["vps"] = (out["ev"] + p["nonop"]) / p["shares"]
    return out


def load_params(wb):
    """Every DCF assumption from Inputs (found by label, formulas evaluated), plus the label -> row map."""
    inp = wb[INPUTS]
    i_rows = {inp.cell(r, 1).value: r for r in range(1, inp.max_row + 1) if inp.cell(r, 1).value}
    cache = {}
    p = {k: (evaluate(wb, INPUTS, f"B{i_rows[label]}", None, cache) if label in i_rows else OPTIONAL[k])
         for k, label in LABELS.items() if k != "override"}
    return p, i_rows


def bridge(p):
    """Net non-operating assets from its parts (as the Inputs formula), for haircut / lease tests."""
    return p["cash_sec"] + (p["eq_inv"] + p["flexport"]) * (1 - p["haircut"]) - p["debt"] - p["leases"]


def with_rates(p, rf=None, mrp=None, beta=None, beta_s=None):
    """Recompute both WACCs (CAPM, no debt) after changing the risk-free rate, MRP or a beta."""
    rf_, mrp_ = p["rf"] if rf is None else rf, p["mrp"] if mrp is None else mrp
    beta_ = (p["wacc"] - p["rf"]) / p["mrp"] if beta is None else beta   # the beta behind today's WACC
    beta_s_ = p["beta_s"] if beta_s is None else beta_s
    return {**p, "rf": rf_, "mrp": mrp_, "beta_s": beta_s_,
            "wacc": rf_ + beta_ * mrp_, "stable_wacc": rf_ + beta_s_ * mrp_}


def bisect(f, target, lo, hi):
    """x in [lo, hi] with f(x) = target; f increasing. Stops within TOL $/share."""
    flo, fhi = f(lo) - target, f(hi) - target
    if flo > 0 or fhi < 0:
        raise ValueError(f"target not bracketed: f({lo})={flo + target:.2f}, f({hi})={fhi + target:.2f}")
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid) - target
        if abs(fm) < TOL:
            return mid
        lo, hi = (mid, hi) if fm < 0 else (lo, mid)
    raise RuntimeError("bisection did not converge")


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    inp, d, rv = wb[INPUTS], wb[DCF], wb[REV]
    p, i_rows = load_params(wb)
    d_rows = {d.cell(r, 1).value: r for r in range(1, d.max_row + 1) if d.cell(r, 1).value}
    override = f"B{i_rows[OVERRIDE]}"
    if inp[override].value is not None:
        sys.exit(f"The growth override ({INPUTS}!{override}) is set; clear it so the base case is the fade.")

    # The Python model must reproduce the workbook before it's trusted
    base = dcf(p)
    wb_vps = evaluate(wb, DCF, f"B{d_rows['Value per share']}")
    wb_ev = evaluate(wb, DCF, f"B{d_rows['Enterprise value']}")
    assert abs(base["vps"] - wb_vps) <= 0.01, (base["vps"], wb_vps)
    assert abs(base["ev"] - wb_ev) <= 0.5, (base["ev"], wb_ev)
    assert abs(bridge(p) - p["nonop"]) < 1e-6, (bridge(p), p["nonop"])
    print(f"Base case reproduced: Python ${base['vps']:.4f} / EV {base['ev']:,.1f}; "
          f"workbook ${wb_vps:.4f} / EV {wb_ev:,.1f}")

    price = p["price"]
    a = bisect(lambda g: dcf(p, g)["vps"], price, -0.5, 1.0)
    b = bisect(lambda g: dcf(p, g)["vps"], base["vps"], -0.5, 1.0)
    c = bisect(lambda m: dcf({**p, "margin10": m})["vps"], price, 0.0, 1.0)
    n = int(p["years"])
    d1 = bisect(lambda g1: dcf(p, lambda t: g1 + (p["g10"] - g1) * (t - 1) / (n - 1))["vps"], price, -0.5, 2.0)
    at_a = dcf(p, a)
    results = {
        RESULTS[0][0]: a, RESULTS[1][0]: b, RESULTS[2][0]: c, RESULTS[3][0]: d1,
        RESULTS[4][0]: at_a["gmv10"], RESULTS[5][0]: at_a["rev10"], RESULTS[6][0]: at_a["gmv10"] / p["gmv0"],
        RESULTS[7][0]: at_a["rev10"] / p["rev0"], RESULTS[8][0]: at_a["fcff10"],
    }

    print(f"\n== Reverse DCF (price ${price:.2f}; base-case value ${base['vps']:.2f})")
    for label, _ in RESULTS[:4]:
        print(f"  {label:48} {results[label]:8.2%}")
    for label, fmt in RESULTS[4:]:
        v = results[label]
        print(f"  {label:48} " + (f"{v:,.0f}" if fmt == "#,##0" else f"{v:.2f}x"))
    print(f"  check: value per share at (a) ${dcf(p, a)['vps']:.4f}, at (b) ${dcf(p, b)['vps']:.4f}, "
          f"at (c) ${dcf({**p, 'margin10': c})['vps']:.4f}")

    # Workbook check: put (a) in the override (in evaluation only) and read the DCF tab
    wb_a = evaluate(wb, DCF, f"B{d_rows['Value per share']}", {(INPUTS, override): a})
    print(f"\n== Workbook DCF with override = (a) {a:.4%}: value per share ${wb_a:.4f} (price ${price:.2f}) "
          f"{'OK' if abs(wb_a - price) <= 0.01 else 'FAIL'}; override cell saved as: {inp[override].value!r}")

    # Write the Results block
    r_rows = {rv.cell(r, 1).value: r for r in range(1, rv.max_row + 1) if rv.cell(r, 1).value}
    note = f"Solved by scripts/reverse.py, {date.today().isoformat()}; re-run if inputs change"
    for label, fmt in RESULTS:
        c_ = rv.cell(r_rows[label], 2)
        c_.value, c_.style, c_.number_format = float(results[label]), "Input", fmt
        rv.cell(r_rows[label], 3).value = note
    wb.save(WORKBOOK)

    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    allowed = {(REV, f"{col}{r_rows[label]}") for label, _ in RESULTS for col in "BC"}
    outside = [k for k in changed if k not in allowed]
    vps_now = evaluate(wb, DCF, f"B{d_rows['Value per share']}")
    print(f"\n== Saved. Cells changed: {len(changed)} (Results block only: {not outside}); "
          f"value per share with override blank: ${vps_now:.2f}")
    print("\n== Reverse tab")
    for r in range(5, wb[REV].max_row + 1):
        lab, cell = wb[REV].cell(r, 1).value, wb[REV].cell(r, 2)
        if lab is None:
            continue
        v = evaluate(wb, REV, cell.coordinate) if cell.value is not None else None
        fmt = cell.number_format
        shown = "" if v is None else f"${v:,.2f}" if fmt.startswith("$") else f"{v:.1%}" if fmt == "0.0%" else \
            f"{v:.1f}x" if "x" in fmt else f"{v:,.0f}"
        print(f"  {lab:48} {shown:>12}")
    if outside or abs(wb_a - price) > 0.01:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
