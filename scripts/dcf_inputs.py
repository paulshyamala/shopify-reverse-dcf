"""Inputs tab: finalise the Forecast section and add the "DCF assumptions" block.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it):
- removes "Terminal FCF margin" (superseded by the FCFF build),
- relabels the starting operating FCF margin as reference only,
- sets the terminal growth rate,
- adds a "DCF assumptions" section: links to Historicals (green), inputs (blue),
  formulas (black), each with a note.
Rows below the removed row move up one; their formulas and the SBC dropdown are
remapped. Refuses to run if the workbook is open in Excel, if another tab
references the rows that move, or if the block already exists. Re-evaluates
WACC, the SBC flag and net non-operating assets, and diffs the workbook.

Usage:
    python scripts/dcf_inputs.py
"""

import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

from build_bridge import REF, evaluate, remap
from build_wacc import clear, fill_refs, find_layout, grab, put, snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
SHEET, HIST = "Inputs", "Historicals"
USD_M, PCT, TAKE = "#,##0", "0.0%", "0.00%"

SECTION, NEW_SECTION = "Forecast", "DCF assumptions"
REMOVE = "Terminal FCF margin"
RELABEL = ("Starting operating FCF margin",
           "Starting operating FCF margin (reference only; superseded by FCFF build)")
TERMINAL_G = ("Terminal growth rate", 0.03,
              "Below Fed long-run nominal GDP (~4%: 2.0% real + 2.0% PCE, SEP Sep 2026)")
CHECKS = ["WACC", "SBC deduction flag", "Net non-operating assets", RELABEL[0]]


def block(hist, rev):
    """(label, kind, value or formula, format, note). {Label} = that row on Inputs."""
    return [
        ("TTM GMV", "link", hist("GMV"), USD_M, "Historicals, TTM Jun-26"),
        ("TTM take rate", "formula", "=IFERROR({" + rev + "}/{TTM GMV},\"\")", TAKE, "Starting revenue / TTM GMV"),
        ("TTM EBIT", "link", hist("Operating income"), USD_M, "Historicals operating income, TTM Jun-26"),
        ("TTM EBIT margin", "formula", "=IFERROR({TTM EBIT}/{" + rev + "},\"\")", PCT, "TTM EBIT / starting revenue"),
        ("GMV growth, year 1", "input", 0.29, PCT, "H1 2026 GMV +33%; Q3 2026 revenue guidance low-30s"),
        ("GMV growth, year 10", "input", 0.07, PCT, "~2× long-run nominal GDP; linear fade from year 1"),
        ("Take rate increase per year", "input", 0.0002, TAKE, "History: 2.63% (FY21) → 3.12% (H1 26)"),
        ("Terminal EBIT margin (year 10)", "input", 0.25, PCT,
         "Linear ramp from TTM. Opex ~34% → ~23% of revenue; PayPal GAAP 18.3% (FY25)"),
        ("Tax rate, year 1", "input", 0.19, PCT, "Effective rate: FY25 18.4%, H1 26 19.3%"),
        ("Tax rate, year 10", "input", 0.24, PCT,
         "Rises as loss carryforwards/credits run out; cash taxes 27 → 347 (FY22 → TTM)"),
        ("D&A % of revenue", "input", 0.002, PCT, "TTM 29 / 13,269"),
        ("Capex % of revenue", "input", 0.002, PCT, "TTM 25 / 13,269"),
        ("Working capital % of revenue increase", "input", 0.04, PCT, "FY25 4.4%, H1 26 4.1%"),
        ("Loan book % of revenue increase", "input", 0.20, PCT,
         "Δ net loan book ÷ Δ revenue: FY23 16.2%, FY24 22.4%, FY25 20.9%"),
    ]


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws, hs = wb[SHEET], wb[HIST]
    _, sections, section_rows = find_layout(ws)
    if NEW_SECTION in section_rows:
        sys.exit(f"{NEW_SECTION!r} already exists; nothing to do.")
    old = {label: r for r, label in sections[SECTION]}
    if REMOVE not in old or RELABEL[0] not in old:
        sys.exit(f"Unexpected {SECTION} rows: {sorted(old)}")
    first, last = section_rows[SECTION] + 1, max(old.values())

    refs = [f"{s.title}!{c.coordinate}" for s in wb if s.title != SHEET for row in s.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=")
            and any(m.group(1) == SHEET and int(m.group(3)) >= old[REMOVE] for m in REF.finditer(c.value))]
    if refs:
        sys.exit(f"Other tabs reference {SHEET} rows that move: {refs}")

    labels = {label: r for rows in sections.values() for r, label in rows}
    old_values = {label: evaluate(wb, SHEET, f"B{labels[label]}") for label in CHECKS}

    # Forecast rows in their current order, minus the removed one
    order = [label for label, r in sorted(old.items(), key=lambda kv: kv[1]) if label != REMOVE]
    saved = {label: grab(ws, old[label]) for label in order}
    row_map = {r: r for r in range(1, first)}
    row_map.update({old[label]: first + i for i, label in enumerate(order)})
    dvs = [dv for dv in ws.data_validations.dataValidation
           if any(first <= rng.min_row <= last for rng in dv.sqref.ranges)]
    section_style = grab(ws, section_rows[SECTION])

    h_header = next(r for r in range(1, hs.max_row + 1) if hs.cell(r, 1).value == "Item")
    h_cols = {hs.cell(h_header, c).value: c for c in range(1, hs.max_column + 1)}
    h_rows = {hs.cell(r, 1).value: r for r in range(h_header + 1, hs.max_row + 1) if hs.cell(r, 1).value}
    hist = lambda label: f"={HIST}!{hs.cell(h_rows[label], h_cols['TTM Jun-26']).coordinate}"
    spec = block(hist, "Starting revenue (TTM)")

    new_section = first + len(order)
    new_rows = {label: new_section + 1 + i for i, (label, *_) in enumerate(spec)}
    for r in range(first, max(last, max(new_rows.values())) + 1):
        clear(ws, r)

    for label in order:
        r = row_map[old[label]]
        put(ws, r, [(remap(v, row_map) if isinstance(v, str) and v.startswith("=") else v, s, c)
                    for v, s, c in saved[label]])
    for dv in dvs:
        dv.sqref = MultiCellRange([CellRange(min_col=rng.min_col, min_row=row_map[rng.min_row],
                                             max_col=rng.max_col, max_row=row_map[rng.max_row])
                                   for rng in dv.sqref.ranges])

    rel = row_map[old[RELABEL[0]]]
    ws.cell(rel, 1).value = RELABEL[1]
    tg = ws.cell(row_map[old[TERMINAL_G[0]]], 2)
    fmt = tg.number_format
    tg.value, tg.style, tg.number_format = TERMINAL_G[1], "Input", fmt
    ws.cell(tg.row, 3).value = TERMINAL_G[2]

    put(ws, new_section, [(NEW_SECTION if i == 0 else v, s, c) for i, (v, s, c) in enumerate(section_style)])
    ref = {label: f"B{r}" for label, r in {**{l: row_map[old[l]] for l in order}, **new_rows}.items()}
    for label, kind, value, fmt, note in spec:
        r = new_rows[label]
        ws.cell(r, 1, label)
        c = ws.cell(r, 2)
        c.value = fill_refs(value, ref) if kind == "formula" else value
        c.style = {"link": "Link", "input": "Input", "formula": "Formula"}[kind]
        c.number_format = fmt
        ws.cell(r, 3, note)

    wb.save(WORKBOOK)
    report(before, old_values, row_map, old, new_section, new_rows)


def report(before, old_values, row_map, old, new_section, new_rows):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]
    labels = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value}

    print(f"== {SECTION} + {NEW_SECTION} (rows {min(row_map[r] for r in old.values() if r in row_map)}-{max(new_rows.values())})")
    for r in range(min(old.values()) - 1, max(new_rows.values()) + 1):
        a, b, c = (ws.cell(r, i) for i in (1, 2, 3))
        if a.value is None:
            continue
        v = evaluate(wb, SHEET, b.coordinate) if b.value is not None else None
        shown = "" if v is None else f"{v:.2%}" if b.number_format in (PCT, TAKE) and isinstance(v, float) else \
            f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)
        print(f"  B{r:<3} {str(a.value)[:58]:58} {shown:>10}  {b.style:7} {str(b.value)[:42]:42} | {c.value or ''}")
    print("  dropdowns:", [(str(dv.sqref), dv.formula1, ws[str(dv.sqref)].offset(0, -1).value)
                           for dv in ws.data_validations.dataValidation])

    ok = True
    print("\n== Unchanged results")
    for label, old_v in old_values.items():
        r = labels.get(label) or labels[RELABEL[1]]
        new_v = evaluate(wb, SHEET, f"B{r}")
        same = old_v == new_v
        ok &= same
        print(f"  {'OK  ' if same else 'DIFF'} {label:32} {new_v}")
    flag, treat = f"B{labels['SBC deduction flag']}", f"B{labels['SBC treatment']}"
    for choice in ("subtract", "ignore"):
        print(f"  SBC treatment {choice:8} -> flag {evaluate(wb, SHEET, flag, {(SHEET, treat): choice})}")

    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    first = min(old.values())
    outside = [k for k in changed if not (k[0] == SHEET and (k[1] == "_validations"
                                                             or int("".join(filter(str.isdigit, k[1]))) >= first))]
    print(f"\n== Cells changed: {len(changed)}; outside Inputs rows >= {first}: {outside or 'none'}")
    if outside or not ok:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
