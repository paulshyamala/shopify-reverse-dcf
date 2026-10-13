"""Write data/historicals.csv into the Historicals tab of the existing workbook.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it), so styles,
data validation and layout are preserved. Rows are matched by their label in
column A and columns by the header row.

- Hardcoded values get the Input style and a source comment.
- Input cells with no value get the ToFill style; a value typed by hand is
  never overwritten by a blank.
- GMV and MRR are left for manual entry.
- Free cash flow and the TTM column are live formulas (Formula style).
- The Ratios section is not touched.

Usage:
    python scripts/fill_historicals.py
"""

import csv
import random
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
CSV_PATH = ROOT / "data" / "historicals.csv"
SHEET = "Historicals"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/1594805/{nodash}/{accn}-index.htm"

PERIOD_COLS = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "H1 2025", "H1 2026"]
TTM_COL = "TTM Jun-26"

# Rows whose TTM is FY2025 + H1 2026 - H1 2025; the rest use the H1 2026 value
FLOW_SECTIONS = {"Income statement", "Cash flow"}
FLOW_KPIS = {"GMV"}
MANUAL_ROWS = ["GMV", "MRR"]
FCF_ROW = "Free cash flow"
OCF_ROW = "Operating cash flow"
CAPEX_ROW = "Capex (purchases of property & equipment)"
SKIP_SECTIONS = {"Ratios"}

# Shopify's reported figures, for validation
EXPECTED = {("Total revenue", "FY2025"): 11556, (FCF_ROW, "FY2025"): 2007}


def find_layout(ws):
    """Header row -> {header: column}; column A below it -> {label: (row, section)}."""
    header_row = next(r for r in range(1, ws.max_row + 1)
                      if ws.cell(r, 1).value == "Item" and ws.cell(r, 2).value == PERIOD_COLS[0])
    cols = {ws.cell(header_row, c).value: c for c in range(1, ws.max_column + 1)
            if ws.cell(header_row, c).value}
    rows, section = {}, None
    for r in range(header_row + 1, ws.max_row + 1):
        label = ws.cell(r, 1).value
        if not label:
            continue
        if ws.cell(r, 1).style == "Section":
            section = label
        else:
            rows[label] = (r, section)
    return cols, rows


def set_style(cell, style):
    """Apply a named style but keep the cell's number format."""
    fmt = cell.number_format
    cell.style = style
    cell.number_format = fmt


def comment(text):
    c = Comment(text, "pull_sec.py")
    c.width, c.height = 320, 140
    return c


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} looks open in Excel ({lock.name} exists). "
                 "Close it first so this write is not overwritten.")

    with CSV_PATH.open() as fh:
        data = list(csv.DictReader(fh))

    wb = load_workbook(WORKBOOK)
    ws = wb[SHEET]
    cols, rows = find_layout(ws)
    letter = {h: ws.cell(1, c).column_letter for h, c in cols.items()}

    missing_rows = {d["item"] for d in data} - rows.keys()
    missing_cols = set(PERIOD_COLS + [TTM_COL]) - cols.keys()
    if missing_rows or missing_cols:
        sys.exit(f"Workbook layout mismatch. Rows not found: {sorted(missing_rows)}; "
                 f"columns not found: {sorted(missing_cols)}")

    written, to_fill = [], []

    # 1. Hardcoded XBRL values
    for d in data:
        cell = ws.cell(rows[d["item"]][0], cols[d["period"]])
        if d["value_usd_m"]:
            cell.value = float(d["value_usd_m"])
            set_style(cell, "Input")
            text = (f"Source: SEC XBRL\nForm: {d['form']}\nAccession: {d['accession_number']}\n"
                    f"Filed: {d['filed_date']}\nPeriod end: {d['period_end']}\nTag: {d['xbrl_tag']}")
            if d["note"]:
                text += f"\nNote: {d['note']}"
            cell.comment = comment(text)
            written.append(d)
        elif cell.value is None:
            set_style(cell, "ToFill")
            cell.comment = comment(f"Not in XBRL. {d['note']}") if d["note"] else None
            to_fill.append((d["item"], d["period"], d["note"]))

    # 2. Manual KPI rows: ToFill unless already typed in
    for label in MANUAL_ROWS:
        for period in PERIOD_COLS:
            cell = ws.cell(rows[label][0], cols[period])
            if cell.value is None:
                set_style(cell, "ToFill")
                to_fill.append((label, period, "Non-GAAP KPI, not in XBRL: enter by hand."))

    # 3. Formulas: FCF per period, then the TTM column
    ocf, capex = rows[OCF_ROW][0], rows[CAPEX_ROW][0]
    for period in PERIOD_COLS:
        c = cols[period]
        cell = ws.cell(rows[FCF_ROW][0], c)
        cell.value = f"={letter[period]}{ocf}-{letter[period]}{capex}"
        set_style(cell, "Formula")
        cell.comment = None

    fy, h1_prev, h1_cur = letter["FY2025"], letter["H1 2025"], letter["H1 2026"]
    for label, (r, section) in rows.items():
        if section in SKIP_SECTIONS:
            continue
        cell = ws.cell(r, cols[TTM_COL])
        if section in FLOW_SECTIONS or label in FLOW_KPIS:
            cell.value = f"={fy}{r}+{h1_cur}{r}-{h1_prev}{r}"
        else:
            cell.value = f"={h1_cur}{r}"
        set_style(cell, "Formula")

    wb.save(WORKBOOK)
    print(f"Wrote {len(written)} values + formulas to {WORKBOOK.relative_to(ROOT)} [{SHEET}]")

    report(data, written, to_fill, rows, cols)


def report(data, written, to_fill, rows, cols):
    values = {(d["item"], d["period"]): float(d["value_usd_m"]) for d in data if d["value_usd_m"]}

    # Re-open and check the workbook still loads, with our styles in place
    wb = load_workbook(WORKBOOK)
    ws = wb[SHEET]
    styles = {ws.cell(rows[d["item"]][0], cols[d["period"]]).style for d in written}
    print(f"Re-opened OK. Styles on hardcoded cells: {styles}. "
          f"Inputs data validations: {len(wb['Inputs'].data_validations.dataValidation)}")

    print("\n== Validation")
    for (item, period), expected in EXPECTED.items():
        if item == FCF_ROW:
            got = values[(OCF_ROW, period)] - values[(CAPEX_ROW, period)]
            how = f"OCF {values[(OCF_ROW, period)]:,.0f} - capex {values[(CAPEX_ROW, period)]:,.0f}"
        else:
            got, how = values[(item, period)], "XBRL"
        diff = got / expected - 1
        flag = "OK" if abs(diff) <= 0.01 else "OFF BY MORE THAN 1%"
        print(f"  {item} {period}: {got:,.0f} ({how}) vs reported {expected:,} -> {diff:+.2%} {flag}")

    print("\n== Historicals (USD m; shares in m). FCF = OCF - capex, as in the formula")
    items = list(dict.fromkeys(d["item"] for d in data))
    items.insert(items.index(CAPEX_ROW) + 1, FCF_ROW)
    print(f"  {'':42}" + "".join(f"{p:>10}" for p in PERIOD_COLS))
    for item in items + MANUAL_ROWS:
        cells = []
        for p in PERIOD_COLS:
            if item == FCF_ROW and (OCF_ROW, p) in values and (CAPEX_ROW, p) in values:
                v = values[(OCF_ROW, p)] - values[(CAPEX_ROW, p)]
            else:
                v = values.get((item, p))
            cells.append(f"{v:>10,.0f}" if v is not None else f"{'MISSING':>10}")
        print(f"  {item:42}" + "".join(cells))

    print("\n== 5 random hardcoded cells to spot-check")
    for d in random.sample(written, 5):
        accn = d["accession_number"].split(";")[0]
        url = ARCHIVE_URL.format(nodash=accn.replace("-", ""), accn=accn)
        print(f"  {d['item']} | {d['period']} | {float(d['value_usd_m']):,.3f} | "
              f"{d['form']} {d['accession_number']} | {url}")

    print("\n== Cells to fill by hand")
    for item, period, note in to_fill:
        print(f"  {item} | {period}: {note}")


if __name__ == "__main__":
    main()
