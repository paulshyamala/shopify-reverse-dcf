"""Pull the cash flow statement detail needed for an FCFF build (SEC XBRL).

For each period, the source filing is the one whose operating cash flow is
already on the Historicals tab (data/historicals.csv), so restatements stay
consistent. From that filing's XBRL:
- calculation linkbase: every line that sums to operating cash flow, with its sign,
- presentation + label linkbases: the line names as printed and which lines sit
  under "Changes in operating assets and liabilities",
- instance: the values.
Also pulls pre-tax income, income tax provision, cash taxes paid, amortization of
acquired intangibles, and Shopify Capital's investing lines. Every period must tie:
net income + non-cash items + changes in operating assets & liabilities = OCF.

Never estimates: anything not disclosed is left blank and reported.
Writes data/cash_flow.csv.

Usage:
    python scripts/pull_fcff.py [--refresh]
"""

import argparse
import csv
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

from pull_sec import (ARCHIVE_URL, COMPANYFACTS_URL, PERIODIC_FORMS, PERIODS, RAW, ROOT,
                      SUBMISSIONS_URL, build_fact_index, companyfacts_facts, facts_for_period,
                      fetch, fetch_instance, instance_facts, load_filings, pick_latest)
from sec_env import sec_user_agent

OUT_CSV = ROOT / "data" / "cash_flow.csv"
HIST_CSV = ROOT / "data" / "historicals.csv"
CF_PERIODS = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "H1 2025", "H1 2026"]

LINK = "{http://www.xbrl.org/2003/linkbase}"
XL = "{http://www.w3.org/1999/xlink}"
OCF = "us-gaap:NetCashProvidedByUsedInOperatingActivities"
INVESTING = "us-gaap:NetCashProvidedByUsedInInvestingActivities"
NET_INCOME = "us-gaap:NetIncomeLoss"
CHANGES_HEADING = "changes in operating assets and liabilities"
SHOPIFY_CAPITAL = ["us-gaap:PaymentsToAcquireLoansHeldForInvestment",
                   "us-gaap:ProceedsFromPrincipalRepaymentsOnLoansAndLeasesHeldForInvestment"]

# Items outside the operating section: (item, candidate tags). Most recent filing wins.
OTHER_ITEMS = [
    ("Income before income taxes", [
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "us-gaap:IncomeLossAttributableToParent"]),
    ("Provision for income taxes", ["us-gaap:IncomeTaxExpenseBenefit"]),
    ("Cash paid for income taxes, net", ["us-gaap:IncomeTaxesPaidNet", "us-gaap:IncomeTaxesPaid"]),
    ("Amortization of acquired intangibles", ["us-gaap:AmortizationOfIntangibleAssets"]),
]

CSV_FIELDS = ["period", "section", "line", "value", "xbrl_tag", "xbrl_value", "weight",
              "form", "accession_number", "period_end"]


def linkbase(accn, kind, refresh):
    path = RAW / "filings" / f"{accn}_{kind}.xml"
    if refresh or not path.exists():
        base = ARCHIVE_URL.format(accn=accn.replace("-", ""))
        index = json.loads(fetch(f"{base}/index.json", RAW / "filings" / f"{accn}-index.json", True))
        name = next(i["name"] for i in index["directory"]["item"] if i["name"].endswith(f"_{kind}.xml"))
        fetch(f"{base}/{name}", path, True)
    return ET.parse(path).getroot()


def concept(href):
    prefix, _, name = href.split("#")[1].partition("_")
    return f"{prefix}:{name}"


def arcs(root, link, arc):
    """{role: [(parent, child, attrs)]} for a calculation or presentation linkbase."""
    out = defaultdict(list)
    for ln in root.iter(f"{LINK}{link}"):
        loc = {l.get(f"{XL}label"): concept(l.get(f"{XL}href")) for l in ln.iter(f"{LINK}loc")}
        for a in ln.iter(f"{LINK}{arc}"):
            out[ln.get(f"{XL}role")].append((loc[a.get(f"{XL}from")], loc[a.get(f"{XL}to")], a.attrib))
    return out


def labels(root):
    """{(concept, label role): text}."""
    loc = {l.get(f"{XL}label"): concept(l.get(f"{XL}href")) for l in root.iter(f"{LINK}loc")}
    res = {(r.get(f"{XL}label"), r.get(f"{XL}role")): (r.text or "").strip()
           for r in root.iter(f"{LINK}label")}
    by_label = defaultdict(list)
    for (lab, role), text in res.items():
        by_label[lab].append((role, text))
    out = {}
    for a in root.iter(f"{LINK}labelArc"):
        for role, text in by_label[a.get(f"{XL}to")]:
            out[(loc[a.get(f"{XL}from")], role)] = text
    return out


def statement(accn, refresh):
    """Operating and investing lines of the cash flow statement in this filing."""
    cal = arcs(linkbase(accn, "cal", refresh), "calculationLink", "calculationArc")
    pre = arcs(linkbase(accn, "pre", refresh), "presentationLink", "presentationArc")
    lab = labels(linkbase(accn, "lab", refresh))
    role = next(r for r, a in cal.items() if any(p == OCF for p, _, _ in a))
    weights = {(p, c): float(at["weight"]) for p, c, at in cal[role]}

    pref = {c: at.get("preferredLabel", "http://www.xbrl.org/2003/role/label") for _, c, at in pre[role]}

    def name(c):
        for r in (pref.get(c), "http://www.xbrl.org/2003/role/terseLabel", "http://www.xbrl.org/2003/role/label"):
            if (c, r) in lab:
                return lab[(c, r)]
        return c

    children = defaultdict(list)
    for p, c, at in pre[role]:
        children[p].append((float(at.get("order", 0)), c))
    heading = [c for c in pref if CHANGES_HEADING in name(c).lower()]
    changes = set()
    for h in heading:
        stack = [h]
        while stack:
            node = stack.pop()
            changes.add(node)
            stack.extend(c for _, c in children[node])

    ordered = [c for _, c in sorted((min(o for o, c2 in children[p] if c2 == c), c)
                                    for p in children for _, c in children[p])]
    order = {c: i for i, c in enumerate(dict.fromkeys(ordered))}
    ops = sorted((c for (p, c) in weights if p == OCF), key=lambda c: order.get(c, 1e9))
    inv = [c for c in SHOPIFY_CAPITAL if (INVESTING, c) in weights]
    return {"ops": ops, "inv": inv, "weights": weights, "changes": changes, "name": name}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download cached SEC data")
    args = parser.parse_args()
    sec_user_agent()  # fail fast if the SEC contact is not configured

    with HIST_CSV.open() as fh:
        ocf_rows = {d["period"]: d for d in csv.DictReader(fh) if d["item"] == "Operating cash flow"}
    sources = {p: ocf_rows[p]["accession_number"] for p in CF_PERIODS}

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

    rows, problems, log = [], [], []
    statements = {accn: statement(accn, args.refresh) for accn in set(sources.values())}

    for period in CF_PERIODS:
        accn = sources[period]
        st, meta = statements[accn], filings[accn]
        own = {k: [f for f in v if f["accn"] == accn] for k, v in index.items()}

        def value(c):
            got = facts_for_period(own.get((c, ()), []), "flow", period)
            return got[0]["val"] / 1e6 if got else None

        base = {"period": period, "form": meta["form"], "accession_number": accn,
                "period_end": PERIODS[period][1]}
        total = 0.0
        for c in st["ops"]:
            v = value(c)
            if v is None:
                continue  # line not used in this period (shown as "—")
            w = st["weights"][(OCF, c)]
            section = ("net_income" if c == NET_INCOME else
                       "op_change" if c in st["changes"] else "non_cash")
            rows.append({**base, "section": section, "line": st["name"](c), "value": round(w * v, 6),
                         "xbrl_tag": c, "xbrl_value": v, "weight": w})
            total += w * v
        ocf = value(OCF)
        rows.append({**base, "section": "ocf", "line": st["name"](OCF), "value": ocf, "xbrl_tag": OCF,
                     "xbrl_value": ocf, "weight": ""})
        if abs(total - ocf) > 0.001:
            problems.append(f"{period}: lines sum to {total:,.3f}, OCF is {ocf:,.3f}")
        for c in st["inv"]:
            v = value(c)
            w = st["weights"][(INVESTING, c)]
            rows.append({**base, "section": "shopify_capital_investing", "line": st["name"](c),
                         "value": "" if v is None else round(w * v, 6), "xbrl_tag": c,
                         "xbrl_value": "" if v is None else v, "weight": w})

        for item, tags in OTHER_ITEMS:
            found = None
            for tag in tags:
                cands = facts_for_period(index.get((tag, ()), []), "flow", period)
                if cands:
                    found = (tag, pick_latest(cands, item, period, (tag, ()), log))
                    break
            row = {"period": period, "section": "other", "line": item, "value": "", "xbrl_tag": "",
                   "xbrl_value": "", "weight": "", "form": "", "accession_number": "",
                   "period_end": PERIODS[period][1]}
            if found:
                tag, f = found
                row.update(value=round(f["val"] / 1e6, 6), xbrl_tag=tag, xbrl_value=f["val"] / 1e6,
                           form=f["form"], accession_number=f["accn"])
            rows.append(row)

    # Pre-tax income - provision must equal net income (guards the tag choice)
    get = lambda p, line: next((r["value"] for r in rows if r["period"] == p and r["line"] == line), "")
    for p in CF_PERIODS:
        pbt, tax = get(p, "Income before income taxes"), get(p, "Provision for income taxes")
        ni = next(r["value"] for r in rows if r["period"] == p and r["section"] == "net_income")
        if pbt == "" or tax == "" or abs(pbt - tax - ni) > 0.001:
            problems.append(f"{p}: pre-tax {pbt} - provision {tax} != net income {ni}")

    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    report(rows, sources, filings, log)
    print(f"\nWrote {len(rows)} rows to {OUT_CSV.relative_to(ROOT)}")
    if problems:
        sys.exit("PROBLEMS:\n  " + "\n  ".join(problems))


def report(rows, sources, filings, log):
    print("== Source filing per period (same filing as Historicals OCF)")
    for p, a in sources.items():
        print(f"  {p:8} {filings[a]['form']:5} {a}")

    by = defaultdict(dict)
    for r in rows:
        by[(r["section"], r["line"], r["xbrl_tag"])][r["period"]] = r["value"]
    order = {"net_income": 0, "non_cash": 1, "op_change": 2, "ocf": 3, "shopify_capital_investing": 4, "other": 5}
    keys = sorted(by, key=lambda k: (order[k[0]], min(i for i, r in enumerate(rows) if (r["section"], r["line"], r["xbrl_tag"]) == k)))
    # Collapse the same tag under different labels into one display line
    merged = {}
    for sec, line, tag in keys:
        key = (sec, tag)
        merged.setdefault(key, {"lines": [], "vals": {}})
        if line not in merged[key]["lines"]:
            merged[key]["lines"].append(line)
        merged[key]["vals"].update(by[(sec, line, tag)])

    def ttm(vals):
        a, b, c = vals.get("FY2025"), vals.get("H1 2026"), vals.get("H1 2025")
        if a in (None, "") or b in (None, "") or c in (None, ""):
            return None
        return a + b - c

    print(f"\n== Cash flow detail (USD m, signs as presented; blank = line not shown that period)")
    print(f"  {'section':12} {'line (as printed, latest)':58}" + "".join(f"{p:>9}" for p in CF_PERIODS) + f"{'TTM':>9}  tag")
    for (sec, tag), d in merged.items():
        vals = d["vals"]
        cells = "".join(f"{vals[p]:>9,.0f}" if vals.get(p) not in (None, "") else f"{'':>9}" for p in CF_PERIODS)
        t = ttm(vals)
        big = any(abs(v) > 50 for v in vals.values() if v not in (None, "")) and sec == "non_cash"
        print(f"  {sec[:12]:12} {d['lines'][-1][:58]:58}{cells}{(f'{t:>9,.0f}' if t is not None else f'{'':>9}')}  "
              f"{(tag.split(':')[1] if tag else '(no fact)')[:48]}{'  >50' if big else ''}")
        if len(d["lines"]) > 1:
            print(f"  {'':12}   (also printed as: {' / '.join(d['lines'][:-1])})")

    print("\n== OCF bridges")
    for target in ("FY2025", "TTM"):
        def sec_sum(sec):
            vs = [ttm(d["vals"]) if target == "TTM" else d["vals"].get(target)
                  for (s, _), d in merged.items() if s == sec]
            return sum(v for v in vs if v not in (None, ""))
        if target == "TTM":
            # TTM per line needs FY2025 and both H1 values; lines missing in an H1
            # statement were not shown there (zero), so sum sections per period instead.
            def per(sec, p):
                return sum(r["value"] for r in rows if r["period"] == p and r["section"] == sec)
            parts = {sec: per(sec, "FY2025") + per(sec, "H1 2026") - per(sec, "H1 2025")
                     for sec in ("net_income", "non_cash", "op_change", "ocf")}
        else:
            parts = {sec: sec_sum(sec) for sec in ("net_income", "non_cash", "op_change", "ocf")}
        gap = parts["net_income"] + parts["non_cash"] + parts["op_change"] - parts["ocf"]
        print(f"  {target}: net income {parts['net_income']:,.0f} + non-cash items {parts['non_cash']:,.0f} "
              f"+ change in operating assets & liabilities {parts['op_change']:,.0f} = "
              f"{parts['net_income'] + parts['non_cash'] + parts['op_change']:,.0f}; reported OCF "
              f"{parts['ocf']:,.0f}; gap {gap:,.3f}")
    if log:
        print("\n".join(log))


if __name__ == "__main__":
    main()
