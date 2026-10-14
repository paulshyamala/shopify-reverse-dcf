"""Pull Shopify historicals from SEC XBRL into data/historicals.csv.

Sources (cached under data/raw/; pass --refresh to re-download):
- companyfacts API: every undimensioned us-gaap / dei fact Shopify has filed.
- submissions API: the filing list, used to show which form covers each period.
- each periodic filing's XBRL instance (*_htm.xml): needed for dimensioned
  facts (segment revenue, cover-page shares by class) and custom shop: tags,
  which the companyfacts API leaves out.

Rules:
- For each item x period, candidate tags are tried in order; the first with a
  fact for that period wins. Some items sum several components (e.g. current
  + noncurrent marketable securities).
- The same fact appears in several filings: the most recently filed one is
  used, so restatements are picked up. Disagreements are logged.
- No match means a blank value. Nothing is estimated or interpolated.

Usage:
    python scripts/pull_sec.py            # use cache where present
    python scripts/pull_sec.py --refresh  # re-download everything
"""

import argparse
import csv
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from pathlib import Path

from sec_env import sec_user_agent

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT_CSV = ROOT / "data" / "historicals.csv"

CIK = "0001594805"
COMPANYFACTS_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
SUBMISSIONS_URL = f"https://data.sec.gov/submissions/CIK{CIK}.json"
ARCHIVE_URL = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{{accn}}"

PERIODIC_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "40-F", "40-F/A", "20-F", "20-F/A"}
ORIGINAL_FORMS = {"10-K", "10-Q", "40-F", "20-F"}

# Period label (matches the Historicals header) -> (start, end).
# Instants use the end date.
PERIODS = {f"FY{y}": (f"{y}-01-01", f"{y}-12-31") for y in range(2021, 2026)}
PERIODS["H1 2025"] = ("2025-01-01", "2025-06-30")
PERIODS["H1 2026"] = ("2026-01-01", "2026-06-30")
DURATION_DAYS = {"FY": (350, 380), "H1": (175, 190)}  # excludes 3-month facts

SUBSCRIPTION = (("srt:ProductOrServiceAxis", "us-gaap:SubscriptionAndCirculationMember"),)
MERCHANT = (("srt:ProductOrServiceAxis", "us-gaap:ServiceMember"),)
CLASS_A = (("us-gaap:StatementClassOfStockAxis", "us-gaap:CommonClassAMember"),)
CLASS_B = (("us-gaap:StatementClassOfStockAxis", "us-gaap:CommonClassBMember"),)


def t(concept, dims=()):
    return (concept, dims)


# (item, kind, candidates). kind: flow = duration fact, stock = instant fact,
# cover = cover page of the period's own filing. Each candidate is a list of
# components that are summed.
ITEMS = [
    ("Total revenue", "flow", [
        [t("us-gaap:Revenues")],
        [t("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax")],
    ]),
    ("Subscription solutions revenue", "flow", [
        [t("us-gaap:Revenues", SUBSCRIPTION)],
        [t("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", SUBSCRIPTION)],
    ]),
    ("Merchant solutions revenue", "flow", [
        [t("us-gaap:Revenues", MERCHANT)],
        [t("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", MERCHANT)],
    ]),
    ("Gross profit", "flow", [[t("us-gaap:GrossProfit")]]),
    ("Operating income", "flow", [[t("us-gaap:OperatingIncomeLoss")]]),
    ("Stock-based compensation", "flow", [
        [t("us-gaap:ShareBasedCompensation")],      # cash flow statement
        [t("us-gaap:StockOptionPlanExpense")],      # Shopify's cash flow statement tag
        [t("us-gaap:AllocatedShareBasedCompensationExpense")],
    ]),
    ("Operating cash flow", "flow", [[t("us-gaap:NetCashProvidedByUsedInOperatingActivities")]]),
    ("Capex (purchases of property & equipment)", "flow", [
        [t("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment")],
        [t("us-gaap:PaymentsToAcquireProductiveAssets")],
    ]),
    ("Cash & equivalents", "stock", [[t("us-gaap:CashAndCashEquivalentsAtCarryingValue")]]),
    ("Marketable securities", "stock", [
        [t("us-gaap:MarketableSecuritiesCurrent"), t("us-gaap:MarketableSecuritiesNoncurrent")],
        [t("us-gaap:ShortTermInvestments")],
    ]),
    ("Equity & other investments", "stock", [
        [t("shop:DebtSecuritiesEquityAndOtherInvestments")],  # balance sheet line
        [t("us-gaap:LongTermInvestments")],
    ]),
    ("Convertible notes / debt", "stock", [
        [t("us-gaap:ConvertibleDebtCurrent"), t("us-gaap:ConvertibleDebtNoncurrent")],
        [t("us-gaap:ConvertibleNotesPayable")],
        [t("us-gaap:LongTermDebt")],
    ]),
    ("Diluted weighted-average shares", "flow", [
        [t("us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding")],
    ]),
    ("Shares outstanding (cover page)", "cover", [
        [t("dei:EntityCommonStockSharesOutstanding", CLASS_A),
         t("dei:EntityCommonStockSharesOutstanding", CLASS_B)],
        [t("dei:EntityCommonStockSharesOutstanding")],
    ]),
]

DEBT_ITEM = "Convertible notes / debt"
DEBT_REPAYMENT_TAGS = ["us-gaap:ProceedsFromConvertibleDebt", "us-gaap:RepaymentsOfConvertibleDebt"]

CSV_FIELDS = ["item", "period", "period_end", "value_usd_m", "xbrl_tag", "form",
              "accession_number", "filed_date", "note"]


# ---------------------------------------------------------------- fetching

def fetch(url, path, refresh):
    if path.exists() and not refresh:
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": sec_user_agent()})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    time.sleep(0.15)  # SEC fair access: stay well under 10 requests/second
    print(f"  downloaded {url}")
    return data


def fetch_instance(accn, refresh):
    """The XBRL instance document of one filing."""
    path = RAW / "filings" / f"{accn}.xml"
    if path.exists() and not refresh:
        return path
    base = ARCHIVE_URL.format(accn=accn.replace("-", ""))
    index = json.loads(fetch(f"{base}/index.json", RAW / "filings" / f"{accn}-index.json", True))
    names = [i["name"] for i in index["directory"]["item"] if i["name"].endswith("_htm.xml")]
    if not names:
        print(f"  WARNING: no XBRL instance in {accn}")
        return None
    fetch(f"{base}/{names[0]}", path, True)
    return path


# ---------------------------------------------------------------- parsing

def load_filings(submissions):
    recent = submissions["filings"]["recent"]
    filings = {}
    for form, filed, report, accn in zip(recent["form"], recent["filingDate"],
                                         recent["reportDate"], recent["accessionNumber"]):
        filings[accn] = {"form": form, "filed": filed, "report": report, "accn": accn}
    if submissions["filings"]["files"]:
        print("  NOTE: older filings are paged out of the submissions index (not needed here)")
    return filings


def companyfacts_facts(companyfacts, filings):
    for ns, tags in companyfacts["facts"].items():
        for tag, body in tags.items():
            for unit_facts in body["units"].values():
                for f in unit_facts:
                    meta = filings.get(f["accn"], {"form": f["form"], "filed": f["filed"]})
                    yield {"concept": f"{ns}:{tag}", "dims": (), "start": f.get("start"),
                           "end": f["end"], "val": float(f["val"]), "accn": f["accn"],
                           "form": meta["form"], "filed": meta["filed"]}


XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"


def instance_facts(path, meta):
    prefixes = {uri: prefix for _, (prefix, uri) in ET.iterparse(path, events=["start-ns"])}
    root = ET.parse(path).getroot()
    contexts = {}
    for ctx in root.findall(f"{XBRLI}context"):
        period = ctx.find(f"{XBRLI}period")
        instant = period.find(f"{XBRLI}instant")
        dims = tuple(sorted((m.get("dimension"), m.text.strip())
                            for m in ctx.iter(f"{XBRLDI}explicitMember")))
        if instant is not None:
            contexts[ctx.get("id")] = (None, instant.text.strip(), dims)
        else:
            contexts[ctx.get("id")] = (period.find(f"{XBRLI}startDate").text.strip(),
                                       period.find(f"{XBRLI}endDate").text.strip(), dims)
    for el in root:
        if el.get("contextRef") is None or el.get("unitRef") is None or not el.text:
            continue
        uri, tag = el.tag[1:].split("}")
        start, end, dims = contexts[el.get("contextRef")]
        yield {"concept": f"{prefixes.get(uri, uri)}:{tag}", "dims": dims, "start": start,
               "end": end, "val": float(el.text), "accn": meta["accn"],
               "form": meta["form"], "filed": meta["filed"]}


def build_fact_index(facts):
    """(concept, dims) -> list of facts, de-duplicated per filing and period."""
    index = defaultdict(dict)
    for f in facts:
        index[(f["concept"], f["dims"])][(f["start"], f["end"], f["accn"])] = f
    return {key: list(v.values()) for key, v in index.items()}


# ---------------------------------------------------------------- selection

def days(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def facts_for_period(facts, kind, label):
    start, end = PERIODS[label]
    if kind == "flow":
        lo, hi = DURATION_DAYS[label[:2]]
        return [f for f in facts if f["start"] and f["end"] == end and lo <= days(f["start"], f["end"]) <= hi]
    return [f for f in facts if f["start"] is None and f["end"] == end]


def tag_name(component):
    concept, dims = component
    if not dims:
        return concept
    return f"{concept}[{', '.join(f'{a}={m}' for a, m in dims)}]"


def pick_latest(candidates, item, label, component, log):
    """Most recently filed fact; logs filings that disagree."""
    chosen = max(candidates, key=lambda f: (f["filed"], f["accn"]))
    values = {f["val"] for f in candidates}
    if len(values) > 1:
        spread = max(values) - min(values)
        kind = "minor, <$1m" if spread < 1e6 else "RESTATED"
        log.append(f"  DISAGREE ({kind}) {item} | {label} | {tag_name(component)}")
        for f in sorted(candidates, key=lambda f: f["filed"]):
            mark = "  <- used" if f is chosen else ""
            log.append(f"      {f['val'] / 1e6:>14,.3f}m  {f['form']:6} {f['accn']} filed {f['filed']}{mark}")
    return chosen


def own_filing(filings, label):
    """The original periodic filing whose report date is the period end."""
    end = PERIODS[label][1]
    own = [f for f in filings.values() if f["form"] in ORIGINAL_FORMS and f["report"] == end]
    return max(own, key=lambda f: f["filed"]) if own else None


def resolve(item, kind, candidates, label, fact_index, filings, log):
    """Value for one item x period, or None. Returns (row dict, matched candidate index)."""
    own = own_filing(filings, label) if kind == "cover" else None
    for idx, components in enumerate(candidates):
        picked = []
        for component in components:
            facts = fact_index.get(component, [])
            if kind == "cover":
                facts = [f for f in facts if own and f["accn"] == own["accn"] and f["start"] is None]
            else:
                facts = facts_for_period(facts, kind, label)
            if facts:
                picked.append((component, pick_latest(facts, item, label, component, log)))
        if not picked:
            continue
        uniq = lambda key: ";".join(dict.fromkeys(f[key] for _, f in picked))
        return {
            "item": item, "period": label,
            "period_end": uniq("end"),
            "value_usd_m": round(sum(f["val"] for _, f in picked) / 1e6, 6),
            "xbrl_tag": " + ".join(tag_name(c) for c, _ in picked),
            "form": uniq("form"), "accession_number": uniq("accn"), "filed_date": uniq("filed"),
            "note": "",
        }, idx
    return None, None


# ---------------------------------------------------------------- reporting

def print_form_types(filings, companyfacts_forms):
    print("\n== Form types filed for each period (from the submissions index)")
    for label, (_, end) in PERIODS.items():
        hits = sorted((f for f in filings.values()
                       if f["report"] == end and (f["form"] in PERIODIC_FORMS or f["form"] == "6-K")),
                      key=lambda f: f["filed"])
        listed = ", ".join(f"{f['form']} {f['accn']} ({f['filed']})" for f in hits) or "none"
        print(f"  {label:8} period end {end}: {listed}")
    print("  Forms carrying XBRL facts in companyfacts:",
          ", ".join(f"{k} ({v})" for k, v in sorted(companyfacts_forms.items())))
    if "6-K" not in companyfacts_forms:
        print("  -> 6-K interim reports carry no XBRL; interim facts exist only from 10-Q filings.")


def debt_blank_note(fact_index, label):
    """Evidence for a blank debt cell: last reported debt value and repayment flows."""
    end = PERIODS[label][1]
    parts = []
    last = []
    for concept in ("us-gaap:ConvertibleDebtCurrent", "us-gaap:ConvertibleDebtNoncurrent"):
        prior = [f for f in fact_index.get((concept, ()), []) if f["start"] is None and f["end"] < end]
        if prior:
            f = max(prior, key=lambda f: (f["end"], f["filed"]))
            last.append(f)
    if last:
        latest_end = max(f["end"] for f in last)
        for f in last:
            if f["end"] == latest_end:
                parts.append(f"last reported {f['concept']} = {f['val'] / 1e6:,.0f} at {f['end']} "
                             f"({f['form']} {f['accn']})")
    for concept in DEBT_REPAYMENT_TAGS:
        sign = -1 if concept.endswith("ProceedsFromConvertibleDebt") else 1
        repaid = [f for f in fact_index.get((concept, ()), [])
                  if f["start"] and f["end"] < end and days(f["start"], f["end"]) > 300
                  and sign * f["val"] > 0]
        if repaid:
            f = max(repaid, key=lambda f: (f["end"], f["filed"]))
            parts.append(f"{concept} = {f['val'] / 1e6:,.0f} for FY{f['end'][:4]} "
                         f"({f['form']} {f['accn']}): notes repaid/settled")
    if not parts:
        return f"No debt fact for {end} in any filing."
    return f"No debt fact for {end} in any filing; " + "; ".join(parts) + "."


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download cached SEC data")
    args = parser.parse_args()
    sec_user_agent()  # fail fast if the SEC contact is not configured

    print("== Loading SEC data")
    companyfacts = json.loads(fetch(COMPANYFACTS_URL, RAW / "companyfacts.json", args.refresh))
    submissions = json.loads(fetch(SUBMISSIONS_URL, RAW / "submissions.json", args.refresh))
    filings = load_filings(submissions)

    facts = list(companyfacts_facts(companyfacts, filings))
    companyfacts_forms = defaultdict(int)
    for f in facts:
        companyfacts_forms[f["form"]] += 1

    print_form_types(filings, companyfacts_forms)

    # Instances of every periodic filing that could report one of our periods
    earliest = min(start for start, _ in PERIODS.values())
    periodic = sorted((f for f in filings.values()
                       if f["form"] in PERIODIC_FORMS and f["filed"] > earliest),
                      key=lambda f: f["filed"])
    print(f"\n== XBRL instances ({len(periodic)} periodic filings since {earliest})")
    for meta in periodic:
        path = fetch_instance(meta["accn"], args.refresh)
        if path:
            facts.extend(instance_facts(path, meta))
            print(f"  {meta['form']:6} {meta['accn']} filed {meta['filed']} (period {meta['report']})")
    fact_index = build_fact_index(facts)

    rows, log, matched = [], [], defaultdict(lambda: defaultdict(list))
    for item, kind, candidates in ITEMS:
        for label in PERIODS:
            row, idx = resolve(item, kind, candidates, label, fact_index, filings, log)
            if row is None:
                note = debt_blank_note(fact_index, label) if item == DEBT_ITEM else "No matching XBRL fact."
                rows.append({"item": item, "period": label, "period_end": PERIODS[label][1],
                             "value_usd_m": "", "xbrl_tag": "", "form": "", "accession_number": "",
                             "filed_date": "", "note": note})
                matched[item]["(none)"].append(label)
                continue
            if kind == "cover":
                row["note"] = (f"Cover page as of {row['period_end']}"
                               + (" (period end)." if row["period_end"] == PERIODS[label][1]
                                  else ", not the period end."))
            if len(candidates[idx]) > 1:
                row["note"] = (row["note"] + " Sum of components.").strip()
            rows.append(row)
            matched[item][row["xbrl_tag"]].append(label)

    # Cover-page counts are as reported on that date, so a later stock split is
    # not applied. Flag any that differ wildly from diluted weighted shares.
    by_key = {(r["item"], r["period"]): r for r in rows}
    for label in PERIODS:
        cover = by_key[("Shares outstanding (cover page)", label)]
        diluted = by_key[("Diluted weighted-average shares", label)]
        if cover["value_usd_m"] and diluted["value_usd_m"]:
            ratio = cover["value_usd_m"] / diluted["value_usd_m"]
            if not 0.5 < ratio < 2:
                cover["note"] += (f" WARNING: {ratio:.2f}x diluted weighted shares for the same period; "
                                  "as reported before a later stock split, not split-adjusted.")

    print("\n== Tags matched per item")
    for item, _, _ in ITEMS:
        for tag, labels in matched[item].items():
            print(f"  {item:42} {tag}  [{', '.join(labels)}]")

    print("\n== Filings that disagree on a value (most recent filing used)")
    print("\n".join(log) if log else "  none")

    blanks = [r for r in rows if r["value_usd_m"] == ""]
    print("\n== Blank values")
    for r in blanks or []:
        print(f"  {r['item']} | {r['period']}: {r['note']}")
    if not blanks:
        print("  none")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {OUT_CSV.relative_to(ROOT)} "
          "(value_usd_m is USD millions; share rows are millions of shares)")


if __name__ == "__main__":
    main()
