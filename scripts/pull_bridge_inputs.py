"""Pull the equity-bridge data points that aren't on the Historicals tab.

- Flexport equity-method investment (balance sheet "Equity method investment")
- basic weighted-average shares, H1 2026
- interest income (income statement "Interest income": interest on marketable
  securities, not Shopify Capital loan revenue), FY2025 / H1 2025 / H1 2026
- operating lease liabilities (current + non-current), Jun 30 2026

Uses the same cached SEC XBRL data and rules as pull_sec.py (most recent filing
wins, six-month durations for H1). Missing values are left blank, never
estimated. Writes data/bridge_inputs.csv.

Usage:
    python scripts/pull_bridge_inputs.py [--refresh]
"""

import argparse
import csv
import json
import sys

from pull_sec import (COMPANYFACTS_URL, PERIODIC_FORMS, PERIODS, RAW, ROOT, SUBMISSIONS_URL,
                      build_fact_index, companyfacts_facts, facts_for_period, fetch,
                      fetch_instance, instance_facts, load_filings, pick_latest)
from sec_env import sec_user_agent

OUT_CSV = ROOT / "data" / "bridge_inputs.csv"

# (item, kind, tag, face-statement line, periods)
ITEMS = [
    ("Flexport equity-method investment", "stock", "us-gaap:EquityMethodInvestments",
     "Balance sheet: Equity method investment", ["FY2025", "H1 2026"]),
    ("Basic weighted-average shares", "flow", "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
     "Income statement: weighted average shares, basic", ["H1 2026"]),
    ("Interest income", "flow", "us-gaap:InterestIncomeExpenseNonoperatingNet",
     "Income statement: Other income, Interest income", ["FY2025", "H1 2025", "H1 2026"]),
    # All of Shopify's leases are operating leases (FY2025 10-K); no finance-lease facts exist
    ("Operating lease liabilities, current", "stock", "us-gaap:OperatingLeaseLiabilityCurrent",
     "Balance sheet: Operating lease liabilities (current liabilities)", ["H1 2026"]),
    ("Operating lease liabilities, non-current", "stock", "us-gaap:OperatingLeaseLiabilityNoncurrent",
     "Balance sheet: Operating lease liabilities (long-term liabilities)", ["H1 2026"]),
]
CHECKS = {("Flexport equity-method investment", "FY2025"): 602}  # Dec 31 2025, FY2025 10-K

CSV_FIELDS = ["item", "period", "period_end", "value_m", "xbrl_tag", "line_item", "form",
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

    rows, log = [], []
    for item, kind, tag, line, periods in ITEMS:
        for period in periods:
            candidates = facts_for_period(index.get((tag, ()), []), kind, period)
            row = {"item": item, "period": period, "period_end": PERIODS[period][1], "value_m": "",
                   "xbrl_tag": tag, "line_item": line, "form": "", "accession_number": "", "filed_date": ""}
            if candidates:
                f = pick_latest(candidates, item, period, (tag, ()), log)
                row.update(value_m=round(f["val"] / 1e6, 6), form=f["form"],
                           accession_number=f["accn"], filed_date=f["filed"])
            rows.append(row)
            shown = f"{row['value_m']:,.3f}m" if row["value_m"] != "" else "BLANK (no fact)"
            print(f"  {item:36} {period:8} {shown:>16}  {tag}  {row['form']} {row['accession_number']}")

    print("\n".join(log) if log else "  (no filings disagree)")

    ok = True
    for (item, period), expected in CHECKS.items():
        got = next(r["value_m"] for r in rows if r["item"] == item and r["period"] == period)
        good = got != "" and abs(got - expected) < 0.5
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {item} {period}: {got} vs expected ≈ {expected}")

    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_CSV.relative_to(ROOT)}")
    if not ok:
        sys.exit("Check failed")


if __name__ == "__main__":
    main()
