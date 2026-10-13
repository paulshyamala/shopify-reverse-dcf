"""Write data/historicals.csv into the Historicals tab of the existing workbook.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it), so styles,
data validation and layout are preserved. Rows are matched by their label in
column A and columns by the header row.

Never overwrites: only empty cells are written, so values, comments and
formulas already in the workbook (including hand edits) are kept. A value that
differs from the CSV is reported, not replaced.

- Hardcoded values get the Input style and a source comment.
- Input cells with no value get the ToFill style.
- GMV is left for manual entry (see scripts/pull_gmv.py); MRR is unused.
- Free cash flow and the TTM column are live formulas (Formula style).
- The Ratios section and the MRR row are not touched.

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
MANUAL_ROWS = ["GMV"]
UNUSED_ROWS = {"MRR"}  # kept so formula references don't shift; never written
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

    written, kept, to_fill = [], 0, []

    # 1. Hardcoded XBRL values, into empty cells only
    for d in data:
        cell = ws.cell(rows[d["item"]][0], cols[d["period"]])
        if cell.value is not None:
            kept += 1
            if d["value_usd_m"] and cell.value != float(d["value_usd_m"]):
                print(f"  KEPT {cell.coordinate} {d['item']} | {d['period']}: workbook has "
                      f"{cell.value}, CSV has {d['value_usd_m']} (not overwritten)")
            continue
        if d["value_usd_m"]:
            cell.value = float(d["value_usd_m"])
            set_style(cell, "Input")
            text = (f"Source: SEC XBRL\nForm: {d['form']}\nAccession: {d['accession_number']}\n"
                    f"Filed: {d['filed_date']}\nPeriod end: {d['period_end']}\nTag: {d['xbrl_tag']}")
            if d["note"]:
                text += f"\nNote: {d['note']}"
            cell.comment = comment(text)
            written.append(d)
        else:
            set_style(cell, "ToFill")
            if d["note"] and cell.comment is None:
                cell.comment = comment(f"Not in XBRL. {d['note']}")
            to_fill.append((d["item"], d["period"], d["note"]))

    # 2. Manual KPI rows: ToFill unless already filled
    for label in MANUAL_ROWS:
        for period in PERIOD_COLS:
            cell = ws.cell(rows[label][0], cols[period])
            if cell.value is None:
                set_style(cell, "ToFill")
                to_fill.append((label, period, "Non-GAAP KPI, not in XBRL: enter by hand."))

    # 3. Formulas, into empty cells only: FCF per period, then the TTM column
    def put_formula(cell, formula):
        nonlocal kept
        if cell.value is not None:
            kept += 1
            return
        cell.value = formula
        set_style(cell, "Formula")

    ocf, capex = rows[OCF_ROW][0], rows[CAPEX_ROW][0]
    for period in PERIOD_COLS:
        put_formula(ws.cell(rows[FCF_ROW][0], cols[period]),
                    f"={letter[period]}{ocf}-{letter[period]}{capex}")

    fy, h1_prev, h1_cur = letter["FY2025"], letter["H1 2025"], letter["H1 2026"]
    for label, (r, section) in rows.items():
        if section in SKIP_SECTIONS or label in UNUSED_ROWS:
            continue
        if section in FLOW_SECTIONS or label in FLOW_KPIS:
            put_formula(ws.cell(r, cols[TTM_COL]), f"={fy}{r}+{h1_cur}{r}-{h1_prev}{r}")
        else:
            put_formula(ws.cell(r, cols[TTM_COL]), f"={h1_cur}{r}")

    wb.save(WORKBOOK)
    print(f"Wrote {len(written)} values to {WORKBOOK.relative_to(ROOT)} [{SHEET}]; "
          f"kept {kept} cells that already had content")

    report(data, to_fill, rows, cols)


def report(data, to_fill, rows, cols):
    # Re-open and report what the workbook now holds (hardcoded numbers only)
    wb = load_workbook(WORKBOOK)
    ws = wb[SHEET]
    items = list(dict.fromkeys(d["item"] for d in data)) + MANUAL_ROWS
    values = {}
    for item in items:
        for p in PERIOD_COLS:
            v = ws.cell(rows[item][0], cols[p]).value
            if isinstance(v, (int, float)):
                values[(item, p)] = float(v)
    hardcoded = [d for d in data if (d["item"], d["period"]) in values and d["value_usd_m"]]
    styles = {ws.cell(rows[d["item"]][0], cols[d["period"]]).style for d in hardcoded}
    print(f"Re-opened OK. Styles on XBRL cells: {styles}. "
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
    items.insert(items.index(CAPEX_ROW) + 1, FCF_ROW)
    print(f"  {'':42}" + "".join(f"{p:>10}" for p in PERIOD_COLS))
    for item in items:
        cells = []
        for p in PERIOD_COLS:
            if item == FCF_ROW and (OCF_ROW, p) in values and (CAPEX_ROW, p) in values:
                v = values[(OCF_ROW, p)] - values[(CAPEX_ROW, p)]
            else:
                v = values.get((item, p))
            cells.append(f"{v:>10,.0f}" if v is not None else f"{'MISSING':>10}")
        print(f"  {item:42}" + "".join(cells))

    print("\n== 5 random hardcoded cells to spot-check")
    for d in random.sample(hardcoded, min(5, len(hardcoded))):
        accn = d["accession_number"].split(";")[0]
        url = ARCHIVE_URL.format(nodash=accn.replace("-", ""), accn=accn)
        print(f"  {d['item']} | {d['period']} | {float(d['value_usd_m']):,.3f} | "
              f"{d['form']} {d['accession_number']} | {url}")

    print("\n== Cells to fill by hand")
    for item, period, note in to_fill:
        print(f"  {item} | {period}: {note}")


if __name__ == "__main__":
    main()
