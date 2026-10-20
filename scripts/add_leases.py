"""Add lease liabilities to the equity bridge (Inputs, balance-sheet block).

Damodaran treats leases as debt. Shopify's leases are all operating leases (FY2025
10-K); the Jun-2026 10-Q values come from data/bridge_inputs.csv (scripts/pull_bridge_inputs.py).
Inserts, directly below "Debt": current and non-current operating lease liabilities
(blue inputs with sources) and "Lease liabilities" (their sum), and subtracts it in
net non-operating assets. Rows are inserted with wb_rows.insert_rows, which rewrites
every reference in the workbook. EBIT is not adjusted for lease expense (simplification).

Refuses to run if the workbook is open in Excel or the rows already exist. Re-evaluates
every formula in the workbook before and after and reports what moved.

Usage:
    python scripts/add_leases.py
"""

import csv
import sys
from pathlib import Path

from openpyxl import load_workbook

from build_dcf import evaluate
from build_wacc import snapshot
from wb_rows import insert_rows

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SRC = ROOT / "data" / "bridge_inputs.csv"
INPUTS = "Inputs"
USD_M = "#,##0"
PARTS = ["Operating lease liabilities, current", "Operating lease liabilities, non-current"]
TOTAL = "Lease liabilities"
NOTE = "Damodaran treats leases as debt; EBIT not adjusted for lease expense (simplification, immaterial)"


def all_values(wb):
    out = {}
    for s in wb:
        cache = {}
        for row in s.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    out[(s.title, c.coordinate, s.cell(c.row, 1).value)] = evaluate(wb, s.title, c.coordinate, None, cache)
    return out


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")
    with SRC.open() as fh:
        src = {d["item"]: d for d in csv.DictReader(fh) if d["period"] == "H1 2026"}
    missing = [x for x in PARTS if src.get(x, {}).get("value_m", "") == ""]
    if missing:
        sys.exit(f"Missing in {SRC.name}: {missing}; run scripts/pull_bridge_inputs.py")

    wb = load_workbook(WORKBOOK)
    before, vals_before = snapshot(wb), all_values(wb)
    ws = wb[INPUTS]
    rows = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value}
    if TOTAL in rows:
        sys.exit("Lease rows already exist; nothing to do.")

    at = rows["Debt"] + 1
    n_changed = insert_rows(wb, INPUTS, at, len(PARTS) + 1)
    for k, label in enumerate(PARTS):
        d = src[label]
        r = at + k
        ws.cell(r, 1, label)
        c = ws.cell(r, 2, float(d["value_m"]))
        c.style, c.number_format = "Input", USD_M
        ws.cell(r, 3, f"{d['xbrl_tag']}, Jun 30 2026, {d['form']} {d['accession_number']}")
    r = at + len(PARTS)
    ws.cell(r, 1, TOTAL)
    c = ws.cell(r, 2, "=" + "+".join(f"B{at + k}" for k in range(len(PARTS))))
    c.style, c.number_format = "Formula", USD_M
    ws.cell(r, 3, NOTE + ". All leases are operating leases (FY2025 10-K); no finance leases.")
    rows = {ws.cell(rr, 1).value: rr for rr in range(1, ws.max_row + 1) if ws.cell(rr, 1).value}
    nonop = ws.cell(rows["Net non-operating assets"], 2)
    nonop.value = nonop.value + f"-B{rows[TOTAL]}"
    note = ws.cell(rows["Net non-operating assets"], 3)
    note.value = (note.value or "") + "; less debt and lease liabilities"

    wb.save(WORKBOOK)
    report(before, vals_before, at, n_changed, rows)


def report(before, vals_before, at, n_changed, rows):
    wb = load_workbook(WORKBOOK)
    after, vals_after = snapshot(wb), all_values(wb)
    ws = wb[INPUTS]
    print(f"Inserted {len(PARTS) + 1} Inputs rows at {at}; formulas rewritten across the workbook: {n_changed}")
    for label in ["Debt"] + PARTS + [TOTAL, "Net non-operating assets", "Implied enterprise value"]:
        r = rows[label]
        print(f"  B{r:<3} {label:42} {str(ws.cell(r, 2).value):18} = {evaluate(wb, INPUTS, f'B{r}'):,.1f}")
    # match before/after by (tab, row label, column) since Inputs rows moved
    key = lambda k: (k[0], k[2], "".join(ch for ch in k[1] if ch.isalpha()))
    b = {key(k): v for k, v in vals_before.items()}
    a = {key(k): v for k, v in vals_after.items()}
    moved = sorted(k for k in b.keys() & a.keys() if b[k] != a[k])
    print(f"\nFormula results changed: {len(moved)} (of {len(b)}); results missing after: {len(b.keys() - a.keys())}")
    for k in moved:
        bv, av = b[k], a[k]
        delta = f"{av - bv:+,.4f}" if isinstance(av, float) and isinstance(bv, float) else ""
        print(f"  {k[0]:12} {str(k[1])[:40]:40} {k[2]}: {bv} -> {av} {delta}")
    for s, lab, chk in (("Inputs", "WACC", 0.10385), ("Inputs", "SBC deduction flag", 1)):
        r = rows[lab]
        print(f"  unchanged? {lab}: {evaluate(wb, s, f'B{r}')}")
    print("  Inputs!B{} (override) blank: {}".format(rows["GMV growth override (constant, all 10 years)"],
                                                     ws.cell(rows["GMV growth override (constant, all 10 years)"], 2).value is None))
    print("  dropdowns:", [str(dv.sqref) for dv in ws.data_validations.dataValidation])


if __name__ == "__main__":
    main()
