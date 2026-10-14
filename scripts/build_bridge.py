"""Step 5: rebuild the Inputs "Market" and "Balance sheet" sections (equity bridge inputs).

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it):
- Market: share price and price date kept as-is; share count built from the
  cover-page basic shares plus treasury-stock dilution; market cap.
- Balance sheet: cash, securities and investments linked to Historicals
  (green Link cells, not retyped), Flexport and interest income from
  data/bridge_inputs.csv (blue inputs with sources), a haircut, net
  non-operating assets, implied EV and the interest-income double-count check.
The WACC and Forecast sections move down; every same-sheet reference in their
formulas and both dropdowns are remapped to the new rows.

Refuses to run if the workbook is open in Excel, if another tab references
Inputs, or if the old Market/Balance sheet rows hold anything it would lose.
Excel isn't available to recalculate, so formulas are evaluated in Python
before and after, and the workbook is diffed.

Usage:
    python scripts/build_bridge.py
"""

import csv
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

from build_wacc import clear, fill_refs, find_layout, grab, put, snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
BRIDGE_CSV = ROOT / "data" / "bridge_inputs.csv"
SHEET, HIST = "Inputs", "Historicals"

USD_M, SHARES, PCT = "#,##0", "#,##0.0", "0.0%"
BALANCE_SECTION = "Balance sheet (as of 2026-06-30)"
OLD_MARKET = {"Share price", "Diluted shares outstanding", "Price date"}
OLD_BALANCE = {"Cash & equivalents", "Marketable securities", "Equity investments", "Debt"}
KEEP = ["Share price", "Price date"]
BOLD = {"Net non-operating assets"}


def accn_note(d, what):
    return f"{d['xbrl_tag']} ({d['line_item']}), {what}, {d['form']} {d['accession_number']}"


def layout(src, hist):
    """New Market and Balance sheet rows: (label, kind, value, format, note).

    kind: keep (moved untouched), link (green, =Historicals!...), input (blue),
    formula (black). {Row label} in formulas refers to that row on Inputs.
    """
    flex, basic_w = src[("Flexport equity-method investment", "H1 2026")], src[("Basic weighted-average shares", "H1 2026")]
    flex_dec = src[("Flexport equity-method investment", "FY2025")]
    interest = {p: src[("Interest income", p)] for p in ("FY2025", "H1 2025", "H1 2026")}
    market = [
        ("Share price", "keep", None, None, None),
        ("Price date", "keep", None, None, None),
        ("Basic shares outstanding", "link", hist("Shares outstanding (cover page)", "H1 2026"), SHARES,
         "Cover page as of 2026-07-31"),
        ("Diluted weighted-average shares (H1 2026)", "link",
         hist("Diluted weighted-average shares", "H1 2026"), SHARES, "Historicals, H1 2026 10-Q"),
        ("Basic weighted-average shares (H1 2026)", "input", float(basic_w["value_m"]), SHARES,
         accn_note(basic_w, "six months to 2026-06-30")),
        ("Dilution from options/RSUs", "formula",
         "={Diluted weighted-average shares (H1 2026)}-{Basic weighted-average shares (H1 2026)}", SHARES,
         "Treasury-stock-method dilution, H1 2026 10-Q"),
        ("Diluted shares outstanding", "formula", "={Basic shares outstanding}+{Dilution from options/RSUs}",
         SHARES, "Used in equity bridge; no extra future dilution since SBC is subtracted"),
        ("Market cap", "formula", "={Share price}*{Diluted shares outstanding}", USD_M, "Sanity check (USD m)"),
    ]
    balance = [
        ("Cash & equivalents", "link", hist("Cash & equivalents", "H1 2026"), USD_M, "Historicals, Jun 30 2026"),
        ("Marketable securities", "link", hist("Marketable securities", "H1 2026"), USD_M,
         "Historicals, Jun 30 2026 (current + long-term)"),
        ("Equity & other investments", "link", hist("Equity & other investments", "H1 2026"), USD_M,
         "Strategic stakes (Affirm, Global-E, Klaviyo, etc.)"),
        ("Flexport (equity method)", "input", float(flex["value_m"]), USD_M,
         accn_note(flex, "Jun 30 2026") + f"; Dec 31 2025: {float(flex_dec['value_m']):,.0f}"),
        ("Debt", "link", hist("Convertible notes / debt", "H1 2026"), USD_M, "Convertible notes settled Nov 2025"),
        ("Haircut on investments", "input", 0.20, PCT,
         "Tax on gains + block discount + private (Flexport) valuation uncertainty"),
        ("Cash & securities (100%)", "formula", "={Cash & equivalents}+{Marketable securities}", USD_M, None),
        ("Investments after haircut", "formula",
         "=({Equity & other investments}+{Flexport (equity method)})*(1-{Haircut on investments})", USD_M, None),
        ("Net non-operating assets", "formula",
         "={Cash & securities (100%)}+{Investments after haircut}-{Debt}", USD_M, "Added to EV in the equity bridge"),
        ("Implied enterprise value", "formula", "={Market cap}-{Net non-operating assets}", USD_M,
         "What the market pays for the operating business"),
    ] + [
        (f"Interest income, {p}", "input", float(d["value_m"]), USD_M, accn_note(d, p)) for p, d in interest.items()
    ] + [
        ("TTM interest income (pre-tax)", "formula",
         "={Interest income, FY2025}+{Interest income, H1 2026}-{Interest income, H1 2025}", USD_M,
         "FY2025 + H1 2026 − H1 2025; interest on marketable securities, not Shopify Capital"),
        ("Tax rate on interest income", "input", 0.25, PCT, "Assumed tax rate on interest income"),
        ("TTM interest income (after tax)", "formula",
         "={TTM interest income (pre-tax)}*(1-{Tax rate on interest income})", USD_M,
         "Embedded in reported FCF; check for double-count vs cash above"),
        ("TTM FCF − SBC", "link", hist("FCF − SBC", "TTM Jun-26"), USD_M, "Historicals, TTM Jun-26"),
        ("Interest as % of TTM FCF − SBC", "formula",
         '=IFERROR({TTM interest income (after tax)}/{TTM FCF − SBC},"")', PCT,
         "≥ 5%: strip after-tax interest from the starting FCF margin (memo/decisions.md §3)"),
    ]
    return market, balance


# ------------------------------------------------------------ formula evaluation

REF = re.compile(r"(?:([A-Za-z]+)!)?\$?([A-Z]{1,3})\$?(\d+)")


def evaluate(wb, sheet, coord, overrides=None, cache=None):
    """Evaluate the formula shapes in this workbook: arithmetic, cross-sheet refs,
    = / <> comparisons, IF, IFERROR(x,""), CHOOSE, MATCH. Blank = 0; text compares
    case-insensitively, like Excel."""
    overrides, cache = overrides or {}, {} if cache is None else cache
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
        expr = REF.sub(ref, expr).replace("{", "[").replace("}", "]").replace("<>", "!=")
        expr = re.sub(r"(?<![<>!=])=(?!=)", "==", expr)
        expr = re.sub(r"IFERROR\(", "IFERROR(lambda: ", expr)
        v = eval(expr, {"__builtins__": {}, "IF": lambda c, a, b: a if c else b,
                        "CHOOSE": lambda i, *xs: xs[int(i) - 1],
                        "MATCH": lambda x, arr, _: arr.index(x) + 1,
                        "IFERROR": _iferror})
    cache[key] = v
    return v


def _iferror(thunk, fallback):
    try:
        return thunk()
    except (ZeroDivisionError, TypeError, ValueError):
        return fallback


# ------------------------------------------------------------ main

def remap(formula, row_map):
    """Point same-sheet references at moved rows; cross-sheet references are left alone."""
    def sub(m):
        if m.group(1):
            return m.group(0)
        old = int(m.group(3))
        if old not in row_map:
            raise ValueError(f"{formula} references row {old}, which is being removed")
        return m.group(0)[: -len(m.group(3))] + str(row_map[old])
    return REF.sub(sub, formula)


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    with BRIDGE_CSV.open() as fh:
        src = {(d["item"], d["period"]): d for d in csv.DictReader(fh)}
    blank = [k for k, d in src.items() if d["value_m"] == ""]
    if blank:
        sys.exit(f"Missing values in {BRIDGE_CSV.name}: {blank}")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    refs = [f"{s.title}!{c.coordinate}" for s in wb if s.title != SHEET for row in s.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=") and f"{SHEET}!" in c.value]
    if refs:
        sys.exit(f"Cells on other tabs reference {SHEET}; moving rows would break them: {refs}")

    ws, hs = wb[SHEET], wb[HIST]
    _, sections, section_rows = find_layout(ws)
    if "Market cap" in {label for rows in sections.values() for _, label in rows}:
        sys.exit("Market / Balance sheet already rebuilt; nothing to do.")
    market_old = {label: r for r, label in sections["Market"]}
    balance_old = {label: r for r, label in sections["Balance sheet"]}
    if set(market_old) != OLD_MARKET or set(balance_old) != OLD_BALANCE:
        sys.exit(f"Unexpected Market/Balance sheet rows: {sorted(market_old)} / {sorted(balance_old)}")
    lost = [label for label, r in {**market_old, **balance_old}.items()
            if label not in KEEP and ws.cell(r, 2).value is not None]
    if lost:
        sys.exit(f"Rows that would be replaced still hold values: {lost}")

    # Historicals cells by label and header
    h_header = next(r for r in range(1, hs.max_row + 1) if hs.cell(r, 1).value == "Item")
    h_cols = {hs.cell(h_header, c).value: c for c in range(1, hs.max_column + 1)}
    h_rows = {hs.cell(r, 1).value: r for r in range(h_header + 1, hs.max_row + 1) if hs.cell(r, 1).value}
    hist = lambda label, period: f"={HIST}!{hs.cell(h_rows[label], h_cols[period]).coordinate}"

    market, balance = layout(src, hist)

    # Evaluate the moving formulas before, to compare after
    tail_start, last = section_rows["WACC"], ws.max_row
    old_values = {r: evaluate(wb, SHEET, f"B{r}") for r in range(tail_start, last + 1)
                  if isinstance(ws.cell(r, 2).value, str) and str(ws.cell(r, 2).value).startswith("=")}

    kept = {label: grab(ws, market_old[label]) for label in KEEP}
    b_section = [(BALANCE_SECTION if i == 0 else v, st, cm)
                 for i, (v, st, cm) in enumerate(grab(ws, section_rows["Balance sheet"]))]
    tail = [grab(ws, r) for r in range(tail_start, last + 1)]
    tail_dvs = [dv for dv in ws.data_validations.dataValidation
                if any(rng.min_row >= tail_start for rng in dv.sqref.ranges)]

    m_sec = section_rows["Market"]
    m_rows = {label: m_sec + 1 + i for i, (label, *_) in enumerate(market)}
    b_sec = m_sec + 1 + len(market)
    b_rows = {label: b_sec + 1 + i for i, (label, *_) in enumerate(balance)}
    new_tail = b_sec + 1 + len(balance)
    shift = new_tail - tail_start
    row_map = {r: r + shift for r in range(tail_start, last + 1)}
    row_map.update({market_old[label]: m_rows[label] for label in KEEP})
    ref = {label: f"B{r}" for label, r in {**m_rows, **b_rows}.items()}

    for r in range(m_sec + 1, max(last, new_tail + len(tail)) + 1):
        clear(ws, r)

    def write(rows_spec, rows_at):
        for label, kind, value, fmt, note in rows_spec:
            r = rows_at[label]
            if kind == "keep":
                put(ws, r, kept[label])
                continue
            ws.cell(r, 1, label)
            cell = ws.cell(r, 2)
            cell.value = fill_refs(value, ref) if kind == "formula" else value
            cell.style = {"link": "Link", "input": "Input", "formula": "Formula"}[kind]
            cell.number_format = fmt
            ws.cell(r, 3, note)
            if label in BOLD:
                ws.cell(r, 1).font = Font(bold=True)
                cell.font = Font(bold=True, color="000000")

    write(market, m_rows)
    put(ws, b_sec, b_section)
    write(balance, b_rows)

    for i, saved in enumerate(tail):
        moved = [(remap(v, row_map) if isinstance(v, str) and v.startswith("=") else v, s, c) for v, s, c in saved]
        put(ws, tail_start + shift + i, moved)
    for dv in tail_dvs:
        dv.sqref = MultiCellRange([CellRange(min_col=rng.min_col, min_row=row_map[rng.min_row],
                                             max_col=rng.max_col, max_row=row_map[rng.max_row])
                                   for rng in dv.sqref.ranges])

    wb.save(WORKBOOK)
    print(f"Market: {len(market)} rows; Balance sheet: {len(balance)} rows; WACC + Forecast moved down "
          f"{shift} rows ({tail_start} -> {tail_start + shift})")
    report(before, old_values, row_map, m_rows, b_rows, kept)


def report(before, old_values, row_map, m_rows, b_rows, kept):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]

    print("\n== New rows, evaluated")
    for label, r in {**m_rows, **b_rows}.items():
        b = ws.cell(r, 2)
        v = evaluate(wb, SHEET, b.coordinate)
        shown = (f"{v:.1%}" if b.number_format == PCT else f"{v:,.1f}" if b.number_format == SHARES
                 else f"{v:,.2f}" if isinstance(v, float) and label == "Share price" else
                 f"{v:,.0f}" if isinstance(v, (int, float)) else str(v))
        print(f"  B{r:<3} {label:42} {shown:>12}  {b.style:7} {str(b.value)[:70]}")

    print("\n== Moved formulas: same result after the move?")
    ok = True
    for old_r, old_v in old_values.items():
        new_r = row_map[old_r]
        new_v = evaluate(wb, SHEET, f"B{new_r}")
        same = old_v == new_v
        ok &= same
        print(f"  {'OK  ' if same else 'DIFF'} B{old_r} -> B{new_r} {ws.cell(new_r, 1).value:32} "
              f"{ws.cell(new_r, 2).value:58} = {new_v}")

    labels = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value}
    print("\n== Dropdowns")
    for dv in ws.data_validations.dataValidation:
        print(f"  {dv.sqref} {dv.formula1} (row label: {ws[str(dv.sqref)].offset(0, -1).value})")
    choice, wacc = f"B{labels['Base-case beta choice']}", f"B{labels['WACC']}"
    treat, flag = f"B{labels['SBC treatment']}", f"B{labels['SBC deduction flag']}"
    for c in ("raw", "adjusted", "industry"):
        print(f"  beta choice {c:9} -> WACC {evaluate(wb, SHEET, wacc, {(SHEET, choice): c}):.4%}")
    for c in ("subtract", "ignore"):
        print(f"  SBC treatment {c:8} -> flag {evaluate(wb, SHEET, flag, {(SHEET, treat): c})}")
    w, f = evaluate(wb, SHEET, wacc), evaluate(wb, SHEET, flag)
    print(f"  as saved: WACC {w:.4%} (Excel shows 10.39%), SBC flag {f}")
    ok &= abs(w - 0.10385) < 1e-9 and f == 1

    print("\n== Kept cells (share price, price date) unchanged?")
    for label in KEEP:
        same = grab(ws, labels[label]) == kept[label]
        ok &= same
        print(f"  {'OK  ' if same else 'DIFF'} {label}: {ws.cell(labels[label], 2).value}")

    tabs = sorted({k[0] for k in before.keys() | after.keys() if before.get(k) != after.get(k)})
    print(f"\n== Tabs changed: {tabs}")
    if tabs != [SHEET] or not ok:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
