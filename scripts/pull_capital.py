"""Pull Shopify Capital balance-sheet and credit-loss data (SEC XBRL).

Balance dates: Dec 31 FY2021-FY2025, Jun 30 2025, Jun 30 2026. Flows: FY2021-FY2025,
H1 2025, H1 2026. Items:
- loans and merchant cash advances, net (balance sheet: current assets only)
- allowance for credit losses, write-offs (net of recoveries) and provision for
  credit losses, split into loans and MCAs where the filing tags the split
  (10-K credit-loss note), otherwise the total
- H1 2024 revenue, for TTM revenue at Jun 30 2025
Most recent filing wins (pull_sec.py rules). Nothing is estimated; missing
values are written blank. Writes data/shopify_capital.csv.

Usage:
    python scripts/pull_capital.py [--refresh]
"""

import argparse
import csv
import json

from pull_sec import (COMPANYFACTS_URL, PERIODIC_FORMS, PERIODS, RAW, ROOT, SUBMISSIONS_URL,
                      build_fact_index, companyfacts_facts, days, facts_for_period, fetch,
                      fetch_instance, instance_facts, load_filings, pick_latest)
from sec_env import sec_user_agent

OUT_CSV = ROOT / "data" / "shopify_capital.csv"
COLS = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "H1 2025", "H1 2026"]
LOANS, MCAS = "FinanceReceivablesMember", "MerchantCashAdvancesMember"

# (item, kind, tag, member: None = undimensioned total, else the loans/MCA member)
ITEMS = [
    ("Loans and MCAs, net: current", "stock", "us-gaap:NotesAndLoansReceivableNetCurrent", None),
    ("Allowance for credit losses: loans", "stock", "us-gaap:AllowanceForNotesAndLoansReceivableCurrent", LOANS),
    ("Allowance for credit losses: MCAs", "stock", "us-gaap:AllowanceForNotesAndLoansReceivableCurrent", MCAS),
    ("Allowance for credit losses (total)", "stock", "us-gaap:AllowanceForNotesAndLoansReceivableCurrent", None),
    ("Write-offs, net of recoveries: loans", "flow",
     "us-gaap:FinancingReceivableAllowanceForCreditLossWriteoffAfterRecovery", LOANS),
    ("Write-offs, net of recoveries: MCAs", "flow",
     "us-gaap:FinancingReceivableAllowanceForCreditLossWriteoffAfterRecovery", MCAS),
    ("Write-offs, net of recoveries (total)", "flow",
     "us-gaap:FinancingReceivableAllowanceForCreditLossWriteoffAfterRecovery", None),
    ("Provision for credit losses: loans", "flow", "us-gaap:ProvisionForLoanLossesExpensed", LOANS),
    ("Provision for credit losses: MCAs", "flow", "us-gaap:ProvisionForLoanLossesExpensed", MCAS),
    ("Provision for credit losses (total)", "flow", "us-gaap:ProvisionForLoanLossesExpensed", None),
]
PRIOR_H1_REVENUE = ("Total revenue, H1 2024", "us-gaap:Revenues", "2024-01-01", "2024-06-30")

CSV_FIELDS = ["item", "period", "period_end", "value_m", "xbrl_tag", "member", "form",
              "accession_number", "filed_date"]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download cached SEC data")
    args = parser.parse_args()
    sec_user_agent()  # fail fast if the SEC contact is not configured

    filings = load_filings(json.loads(fetch(SUBMISSIONS_URL, RAW / "submissions.json", args.refresh)))
    facts = list(companyfacts_facts(
        json.loads(fetch(COMPANYFACTS_URL, RAW / "companyfacts.json", args.refresh)), filings))
    earliest = min(start for start, _ in PERIODS.values())
    for meta in sorted(filings.values(), key=lambda f: f["filed"]):
        if meta["form"] in PERIODIC_FORMS and meta["filed"] > earliest:
            path = fetch_instance(meta["accn"], args.refresh)
            if path:
                facts.extend(instance_facts(path, meta))
    index = build_fact_index(facts)

    def series(tag, member):
        """All facts for a tag, undimensioned or with exactly this one member."""
        out = []
        for (concept, dims), fs in index.items():
            if concept != tag:
                continue
            if member is None and dims == ():
                out += fs
            elif member and len(dims) == 1 and dims[0][1].endswith(member):
                out += fs
        return out

    rows, log = [], []
    for item, kind, tag, member in ITEMS:
        facts_ = series(tag, member)
        for p in COLS:
            cands = facts_for_period(facts_, kind, p)
            row = {"item": item, "period": p, "period_end": PERIODS[p][1], "value_m": "", "xbrl_tag": tag,
                   "member": member or "", "form": "", "accession_number": "", "filed_date": ""}
            if cands:
                f = pick_latest(cands, item, p, (tag, ((("member", member),) if member else ())), log)
                row.update(value_m=round(f["val"] / 1e6, 6), form=f["form"],
                           accession_number=f["accn"], filed_date=f["filed"])
            rows.append(row)

    item, tag, start, end = PRIOR_H1_REVENUE
    cands = [f for f in index.get((tag, ()), []) if f["start"] == start and f["end"] == end]
    f = pick_latest(cands, item, "H1 2024", (tag, ()), log) if cands else None
    rows.append({"item": item, "period": "H1 2024", "period_end": end,
                 "value_m": round(f["val"] / 1e6, 6) if f else "", "xbrl_tag": tag, "member": "",
                 "form": f["form"] if f else "", "accession_number": f["accn"] if f else "",
                 "filed_date": f["filed"] if f else ""})

    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"  {'':40}" + "".join(f"{p:>10}" for p in COLS))
    for item, *_ in ITEMS:
        vals = {r["period"]: r["value_m"] for r in rows if r["item"] == item}
        print(f"  {item:40}" + "".join(f"{vals[p]:>10,.1f}" if vals[p] != "" else f"{'BLANK':>10}" for p in COLS))
    r = rows[-1]
    print(f"  {r['item']}: {r['value_m']} ({r['form']} {r['accession_number']})")
    print("\n".join(log) if log else "  (no filings disagree)")
    print(f"Wrote {len(rows)} rows to {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
