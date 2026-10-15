"""Add Shopify Capital loan-book rows to the Historicals FCFF sections.

Opens model/shopify_reverse_dcf.xlsx in place (never rebuilds it):
- "FCFF data": blue inputs with source comments from data/shopify_capital.csv
  (net loan book, allowance, write-offs, provision for credit losses; loans/MCA
  split where tagged, total formula where both parts exist, reported total
  otherwise), plus prior-year H1 revenue for TTM revenue at Jun 30 2025.
- the "FCFF build" section moves down to make room; its same-sheet formulas
  are remapped (cross-sheet links untouched) and re-evaluated to prove the
  results didn't change.
- "FCFF build": loan book / TTM revenue, change in loan book, change in loan
  book / change in revenue, and the lending cash flow vs loan book check.

Refuses to run if the workbook is open in Excel, if another tab references
the rows that move, or if the rows already exist. Diffs the workbook after.

Usage:
    python scripts/fill_capital.py
"""

import csv
import re
import sys
from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font

from build_bridge import REF, evaluate
from build_wacc import snapshot

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "model" / "shopify_reverse_dcf.xlsx"
CAP_CSV = ROOT / "data" / "shopify_capital.csv"
SHEET = "Historicals"

PERIODS = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "H1 2025", "H1 2026"]
TTM = "TTM Jun-26"
COLS = PERIODS + [TTM]
FY = PERIODS[:5]
FY_PRIOR = {"FY2022": "FY2021", "FY2023": "FY2022", "FY2024": "FY2023", "FY2025": "FY2024"}
USD_M, PCT, GREY = "#,##0", "0.0%", "808080"

DATA_SECTION = "FCFF data (cash flow statement; outflows negative)"
BUILD_SECTION = "FCFF build"
REV = "Total revenue"
LENDING = "Net Shopify Capital lending"

BOOK = "Loans and MCAs, net: current"
BOOK_NC = "Loans and MCAs, net: non-current"
BOOK_TOTAL = "Loans and MCAs, net (total)"
GROUPS = [  # (loans row, MCAs row, total row, balance item?)
    ("Allowance for credit losses: loans", "Allowance for credit losses: MCAs", "Allowance for credit losses (total)", True),
    ("Write-offs, net of recoveries: loans", "Write-offs, net of recoveries: MCAs", "Write-offs, net of recoveries (total)", False),
    ("Provision for credit losses: loans", "Provision for credit losses: MCAs", "Provision for credit losses (total)", False),
]
PRIOR_H1 = "Total revenue, prior-year H1"
NOTE_BAL = "Credit-loss note / balance sheet; balance at period end"


def grab(ws, r, ncols):
    out = []
    for c in range(1, ncols + 1):
        cell = ws.cell(r, c)
        out.append((cell.value, copy(cell._style), (cell.comment.text, cell.comment.author) if cell.comment else None))
    return out


def put(ws, r, saved):
    for c, (value, style, cm) in enumerate(saved, start=1):
        cell = ws.cell(r, c)
        cell.value, cell._style = value, copy(style)
        cell.comment = Comment(*cm) if cm else None


def clear(ws, r, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(r, c)
        cell.value, cell.comment = None, None
        cell.style = "Normal"


def shift_refs(formula, start, n):
    """Same-sheet references to rows >= start move down n rows; Sheet!A1 refs are left alone."""
    def sub(m):
        if m.group(1):
            return m.group(0)
        row = int(m.group(3))
        return m.group(0) if row < start else m.group(0)[: -len(m.group(3))] + str(row + n)
    return REF.sub(sub, formula)


def main():
    lock = WORKBOOK.with_name(f"~${WORKBOOK.name}")
    if lock.exists():
        sys.exit(f"{WORKBOOK.name} is open in Excel ({lock.name} exists). Close it and re-run.")

    with CAP_CSV.open() as fh:
        src = {(d["item"], d["period"]): d for d in csv.DictReader(fh)}

    wb = load_workbook(WORKBOOK)
    before = snapshot(wb)
    ws = wb[SHEET]
    header = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Item")
    cols = {ws.cell(header, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(header, c).value}
    ncols = cols["Source / notes"]
    rows = {ws.cell(r, 1).value: r for r in range(header + 1, ws.max_row + 1) if ws.cell(r, 1).value}
    if BOOK in rows:
        sys.exit("Shopify Capital rows already added; nothing to do.")
    start, last = rows[BUILD_SECTION], max(rows.values())

    # Nothing else may point at the rows that move
    refs = [f"{s.title}!{c.coordinate}" for s in wb if s.title != SHEET for row in s.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=")
            and any(int(m.group(3)) >= start for m in REF.finditer(c.value) if m.group(1) == SHEET)]
    if refs:
        sys.exit(f"Other tabs reference Historicals rows >= {start}: {refs}")

    L = {p: ws.cell(1, cols[p]).column_letter for p in COLS}
    moved_formulas = {(r, c): evaluate(wb, SHEET, ws.cell(r, c).coordinate)
                      for r in range(start, last + 1) for c in range(2, ncols)
                      if isinstance(ws.cell(r, c).value, str) and str(ws.cell(r, c).value).startswith("=")}
    saved = [grab(ws, r, ncols) for r in range(start, last + 1)]

    data_labels = [BOOK, BOOK_NC, BOOK_TOTAL] + [lab for g in GROUPS for lab in g[:3]] + [PRIOR_H1]
    n = len(data_labels)
    for r in range(start, last + n + 1):
        clear(ws, r, ncols)
    for i, s in enumerate(saved):
        put(ws, start + n + i, [(shift_refs(v, start, n) if isinstance(v, str) and v.startswith("=") else v, st, cm)
                                for v, st, cm in s])
    rows = {ws.cell(r, 1).value: r for r in range(header + 1, ws.max_row + 1) if ws.cell(r, 1).value}
    new = {label: start + i for i, label in enumerate(data_labels)}

    def cell(r, p, value, style, fmt=USD_M, cm=None):
        c = ws.cell(r, cols[p])
        c.value, c.style, c.number_format = value, style, fmt
        if cm:
            c.comment = Comment(cm, "fill_capital.py")
        return c

    def na(r, p, note, fmt=USD_M):
        c = cell(r, p, "n/a", "Formula", fmt, note)
        c.font, c.alignment = Font(color=GREY), Alignment(horizontal="right")

    def source(d):
        member = f" [{d['member']}]" if d["member"] else ""
        return (f"Source: SEC XBRL\nForm: {d['form']}\nAccession: {d['accession_number']}\n"
                f"Period end: {d['period_end']}\nTag: {d['xbrl_tag']}{member}")

    def put_input(r, p, d):
        c = cell(r, p, float(d["value_m"]), "Input")
        c.comment = Comment(source(d), "fill_capital.py")
        c.comment.width, c.comment.height = 340, 130

    def label_row(label, note):
        r = new[label]
        ws.cell(r, 1, label)
        ws.cell(r, ncols, note)
        return r

    has = lambda item, p: src.get((item, p), {}).get("value_m", "") != ""

    # Net loan book
    r = label_row(BOOK, "Balance sheet: 'Loans and merchant cash advances, net' (current assets)")
    for p in PERIODS:
        put_input(r, p, src[(BOOK, p)])
    cell(r, TTM, f"={L['H1 2026']}{r}", "Formula")
    r = label_row(BOOK_NC, "No such line")
    for p in COLS:
        na(r, p, "No non-current line: the balance sheet shows 'Loans and merchant cash advances, net' "
                 "only in current assets.")
    r = label_row(BOOK_TOTAL, "Equals current (no non-current line)")  # notes must not start with "=" (openpyxl would store a formula)
    for p in COLS:
        cell(r, p, f"={L[p]}{new[BOOK]}", "Formula")

    # Allowance, write-offs, provision: loans/MCA split where tagged, else the reported total
    for loans, mcas, total, balance in GROUPS:
        rl, rm, rt = label_row(loans, NOTE_BAL if balance else "Credit-loss note"), \
            label_row(mcas, NOTE_BAL if balance else "Credit-loss note"), \
            label_row(total, "Sum of loans + MCAs where split; reported total otherwise")
        for p in PERIODS:
            if has(loans, p) and has(mcas, p):
                put_input(rl, p, src[(loans, p)])
                put_input(rm, p, src[(mcas, p)])
                cell(rt, p, f"={L[p]}{rl}+{L[p]}{rm}", "Formula")
            elif has(total, p):
                note = "Split not tagged in this filing; only the total is reported."
                na(rl, p, note)
                na(rm, p, note)
                put_input(rt, p, src[(total, p)])
            else:
                for rr in (rl, rm, rt):
                    cell(rr, p, None, "ToFill", USD_M, "Not found in XBRL; left blank.")
        if balance:
            for rr in (rl, rm, rt):
                cell(rr, TTM, f"={L['H1 2026']}{rr}", "Formula")
        else:
            cell(rt, TTM, f"={L['FY2025']}{rt}+{L['H1 2026']}{rt}-{L['H1 2025']}{rt}", "Formula")
            for rr in (rl, rm):
                na(rr, TTM, "H1 2026 split not tagged; TTM only for the total.")

    # Prior-year H1 revenue, for TTM revenue at Jun 30
    r = label_row(PRIOR_H1, "H1 2025 column: H1 2024 revenue; H1 2026 column: H1 2025 revenue")
    for p in FY + [TTM]:
        na(r, p, "Only needed for the H1 columns.")
    put_input(r, "H1 2025", src[("Total revenue, H1 2024", "H1 2024")])
    cell(r, "H1 2026", f"={L['H1 2025']}{rows[REV]}", "Formula")

    # ---------------- FCFF build: new rows at the end
    nxt = [max(rows.values()) + 1]  # rows already reflects the moved build section
    rows.update(new)

    def build(label, note=None):
        r = nxt[0]
        nxt[0] += 1
        ws.cell(r, 1, label)
        if note:
            ws.cell(r, ncols, note)
        rows[label] = r
        return r

    rev, book = rows[REV], rows[BOOK_TOTAL]
    r = build("TTM revenue at balance date", "FY: fiscal-year revenue; Jun 30: trailing twelve months")
    for p in FY:
        cell(r, p, f"={L[p]}{rev}", "Formula")
    cell(r, "H1 2025", f"={L['FY2024']}{rev}+{L['H1 2025']}{rev}-{L['H1 2025']}{rows[PRIOR_H1]}", "Formula")
    cell(r, "H1 2026", f"={L['FY2025']}{rev}+{L['H1 2026']}{rev}-{L['H1 2026']}{rows[PRIOR_H1]}", "Formula")
    cell(r, TTM, f"={L[TTM]}{rev}", "Formula")
    ttm_rev = r

    r = build("Net loan book ÷ TTM revenue")
    for p in COLS:
        cell(r, p, f'=IFERROR({L[p]}{book}/{L[p]}{ttm_rev},"")', "Formula", PCT)

    na_chg = "No prior balance date in the workbook (Dec 2020 / Jun 2024)."
    r = build("Change in net loan book", "FY: vs prior Dec 31; TTM: Jun 30 2026 vs Jun 30 2025")
    for p in COLS:
        if p in FY_PRIOR:
            cell(r, p, f"={L[p]}{book}-{L[FY_PRIOR[p]]}{book}", "Formula")
        elif p == TTM:
            cell(r, p, f"={L['H1 2026']}{book}-{L['H1 2025']}{book}", "Formula")
        else:
            na(r, p, na_chg)
    chg = r

    r = build("Change in net loan book ÷ change in revenue")
    for p in COLS:
        if p in FY_PRIOR:
            cell(r, p, f'=IFERROR({L[p]}{chg}/({L[p]}{rev}-{L[FY_PRIOR[p]]}{rev}),"")', "Formula", PCT)
        elif p == TTM:
            cell(r, p, f'=IFERROR({L[p]}{chg}/({L["H1 2026"]}{ttm_rev}-{L["H1 2025"]}{ttm_rev}),"")', "Formula", PCT)
        else:
            na(r, p, na_chg, PCT)

    wo, prov = rows["Write-offs, net of recoveries (total)"], rows["Provision for credit losses (total)"]
    na_lend = "Net lending incl. MCAs is FY only (H1 MCA change not disclosed)."
    r = build("Check: net lending cash flow − write-offs", "Net Shopify Capital lending − write-offs")
    for p in COLS:
        if p in FY:
            cell(r, p, f"={L[p]}{rows[LENDING]}-{L[p]}{wo}", "Formula")
        else:
            na(r, p, na_lend)
    check = r
    r = build("Gap: change in loan book − (lending − write-offs)")
    for p in COLS:
        if p in FY_PRIOR:
            cell(r, p, f"={L[p]}{chg}-{L[p]}{check}", "Formula")
        else:
            na(r, p, na_lend if p not in FY else na_chg)
    gap = r
    r = build("Allowance build (provision − write-offs)", "Raises the allowance, so lowers the net book")
    for p in COLS:
        cell(r, p, f"={L[p]}{prov}-{L[p]}{wo}", "Formula")
    build_r = r
    r = build("Gap after allowance build", "Gap + allowance build; rest = fees accrued vs collected, FX, timing")
    for p in COLS:
        if p in FY_PRIOR:
            cell(r, p, f"={L[p]}{gap}+{L[p]}{build_r}", "Formula")
        else:
            na(r, p, na_lend if p not in FY else na_chg)

    wb.save(WORKBOOK)
    report(before, moved_formulas, n, start, new, rows, nxt[0])


def report(before, moved_formulas, n, start, new, rows, end):
    wb = load_workbook(WORKBOOK)
    after = snapshot(wb)
    ws = wb[SHEET]
    header = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Item")
    cols = {ws.cell(header, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(header, c).value}

    diffs = [(r, c, old, evaluate(wb, SHEET, ws.cell(r + n, c).coordinate))
             for (r, c), old in moved_formulas.items()]
    bad = [d for d in diffs if d[2] != d[3]]
    print(f"== FCFF build moved down {n} rows ({start} -> {start + n}); {len(diffs)} formulas re-evaluated, "
          f"{len(bad)} changed")
    for d in bad:
        print("   ", d)

    shown = list(new.items()) + [(ws.cell(r, 1).value, r) for r in range(end - 9, end)]
    print(f"\n== New rows, evaluated (USD m)")
    print(f"  {'':46}" + "".join(f"{p:>10}" for p in COLS))
    for label, r in shown:
        out = []
        for p in COLS:
            c = ws.cell(r, cols[p])
            v = evaluate(wb, SHEET, c.coordinate) if c.value is not None else None
            out.append(f"{'':>10}" if v is None else f"{v:>10}" if isinstance(v, str) else
                       f"{v:>10.1%}" if c.number_format == PCT else f"{v:>10,.0f}")
        print(f"  r{r:<3}{label[:42]:42}" + "".join(out))

    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    outside = [k for k in changed if k[0] != SHEET or k[1] == "_validations"
               or int("".join(filter(str.isdigit, k[1]))) < start]
    print(f"\n== Cells changed: {len(changed)}; outside Historicals rows >= {start}: {outside or 'none'}")
    if bad or outside:
        sys.exit("Validation failed")


if __name__ == "__main__":
    main()
