"""Extract Shopify GMV from filing text (MD&A "Key Performance Indicators").

GMV is a non-GAAP KPI, so it is not in XBRL. This reads the KPI table of each
filing's MD&A, picks the column by its header (year, and the six-month group
for H1), and writes data/gmv.csv with a verbatim source reference.

Filing documents are cached under data/raw/docs/<accession>/ (--refresh to
re-download). A value that can't be found unambiguously is left blank.

Usage:
    python scripts/pull_gmv.py [--refresh]
"""

import argparse
import csv
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "raw" / "docs"
OUT_CSV = ROOT / "data" / "gmv.csv"

USER_AGENT = "REDACTED"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/1594805/{nodash}/{doc}"

SECTION = "Key Performance Indicators"
ROW_LABEL = "Gross Merchandise Volume"
MDA_10Q = "Part I, Item 2: Management's Discussion and Analysis"

# accession -> (form, document, exhibit or item holding the MD&A)
FILINGS = {
    "0001594805-22-000011": ("40-F", "exhibit13mda2021.htm", "Exhibit 1.3 (MD&A)"),
    "0001594805-23-000011": ("40-F", "exhibit13mda2022.htm", "Exhibit 1.3 (MD&A)"),
    "0001594805-24-000007": ("40-F", "exhibit13mdaq42023.htm", "Exhibit 1.3 (MD&A)"),
    "0001594805-25-000012": ("10-K", "shop-20241231.htm", "Item 7: Management's Discussion and Analysis"),
    "0001594805-26-000007": ("10-K", "shop-20251231.htm", "Item 7: Management's Discussion and Analysis"),
    "0001594805-25-000073": ("10-Q", "shop-20250630.htm", MDA_10Q),
    "0001594805-25-000089": ("10-Q", "shop-20250930.htm", MDA_10Q),
    "0001594805-26-000019": ("10-Q", "shop-20260331.htm", MDA_10Q),
    "0001594805-26-000047": ("10-Q", "shop-20260630.htm", MDA_10Q),
}

# Historicals period -> (accession, column group, column year)
PICKS = {
    "FY2021": ("0001594805-22-000011", "Years ended", "2021"),
    "FY2022": ("0001594805-23-000011", "Years ended", "2022"),
    "FY2023": ("0001594805-24-000007", "Years ended", "2023"),
    "FY2024": ("0001594805-25-000012", "Years ended", "2024"),
    "FY2025": ("0001594805-26-000007", "Years ended", "2025"),
    "H1 2025": ("0001594805-26-000047", "Six months", "2025"),
    "H1 2026": ("0001594805-26-000047", "Six months", "2026"),
}

EXPECTED = {"FY2024": 292275, "FY2025": 378441}  # Shopify's reported GMV, USD m

CSV_FIELDS = ["period", "value_usd_m", "as_reported", "units", "form", "accession_number",
              "document", "exhibit_or_item", "section", "intro_sentence", "table_row", "column"]


class _Text(HTMLParser):
    """HTML -> lines of text; table cells separated by ' | '."""
    BLOCK = {"p", "div", "tr", "br", "li", "h1", "h2", "h3", "h4", "table"}
    HIDDEN = {"script", "style", "ix:header"}

    def __init__(self):
        super().__init__()
        self.out, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        self.hidden += tag in self.HIDDEN
        if tag in self.BLOCK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        self.hidden -= tag in self.HIDDEN
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.out.append(data)


def doc_lines(accn, refresh):
    form, doc, _ = FILINGS[accn]
    path = DOCS / accn / doc
    if refresh or not path.exists():
        url = DOC_URL.format(nodash=accn.replace("-", ""), doc=doc)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        time.sleep(0.15)
        print(f"  downloaded {url}")
    parser = _Text()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    text = "".join(parser.out).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"( \| )+( ?\| ?)*", " | ", text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def cells(line):
    return [c.strip() for c in line.split("|") if c.strip()]


def kpi_table(lines):
    """Parse the GMV row of the KPI table that follows the section heading."""
    starts = [i for i, line in enumerate(lines) if line == SECTION]
    for start in starts:
        rows = [i for i in range(start, min(start + 40, len(lines)))
                if lines[i].startswith(f"| {ROW_LABEL} |")]
        if not rows:
            continue
        r = rows[0]
        block = lines[start:r]
        year_idx = max(i for i, line in enumerate(block) if re.fullmatch(r"[|\s\d]+", line)
                       and re.search(r"\d{4}", line))
        years = cells(block[year_idx])
        groups = cells(block[year_idx - 1])
        units = next(line for line in block if "(in " in line)
        intro = next((line for line in block if line.startswith("The following table shows")), "")
        values = [c for c in cells(lines[r])[1:] if c != "$"]
        if len(values) != len(years) or len(years) % len(groups):
            raise ValueError(f"table shape mismatch: {groups} {years} {values}")
        per_group = len(years) // len(groups)
        columns = [(groups[i // per_group], years[i], values[i]) for i in range(len(years))]
        scale = 1 / 1000 if "thousands" in units else 1 if "millions" in units else None
        if scale is None:
            raise ValueError(f"unknown units: {units}")
        return {"columns": columns, "units": units.strip("| ").strip(), "scale": scale,
                "intro": intro, "row": lines[r].strip("| ").strip()}
    return None


def value_for(table, group, year):
    hits = [v for g, y, v in table["columns"] if g.startswith(group) and y == year]
    if len(hits) != 1:
        return None, None
    return hits[0], float(hits[0].replace(",", "")) * table["scale"]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download filing documents")
    args = parser.parse_args()

    tables = {}
    for accn in FILINGS:
        tables[accn] = kpi_table(doc_lines(accn, args.refresh))
        if tables[accn] is None:
            print(f"  WARNING: no '{ROW_LABEL}' row under '{SECTION}' in {accn}")

    rows = []
    for period, (accn, group, year) in PICKS.items():
        form, doc, where = FILINGS[accn]
        table = tables[accn]
        raw, value = value_for(table, group, year) if table else (None, None)
        if value is None:
            print(f"  {period}: not found unambiguously in {accn}; left blank")
        group_label = next((g for g, y, _ in table["columns"] if g.startswith(group)), group) if table else ""
        rows.append({
            "period": period, "value_usd_m": "" if value is None else round(value, 3),
            "as_reported": raw or "", "units": table["units"] if table else "",
            "form": form, "accession_number": accn, "document": doc, "exhibit_or_item": where,
            "section": SECTION, "intro_sentence": table["intro"] if table else "",
            "table_row": table["row"] if table else "", "column": f"{group_label} {year}",
        })

    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_CSV.relative_to(ROOT)}")

    checks(rows, tables)


def checks(rows, tables):
    got = {r["period"]: r["value_usd_m"] for r in rows if r["value_usd_m"] != ""}
    ok = True

    def check(label, a, b):
        nonlocal ok
        good = abs(a - b) < 0.5
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {label}: {a:,.0f} vs {b:,.0f}")

    def col(accn, group, year):
        return value_for(tables[accn], group, year)[1]

    print("\n== Sanity checks")
    for period, expected in EXPECTED.items():
        check(f"{period} vs Shopify reported", got[period], expected)
    q1_26, q2_26 = col("0001594805-26-000019", "Three", "2026"), col("0001594805-26-000047", "Three", "2026")
    q1_25, q2_25 = col("0001594805-26-000019", "Three", "2025"), col("0001594805-26-000047", "Three", "2025")
    check("H1 2026 = Q1 + Q2 2026", got["H1 2026"], q1_26 + q2_26)
    check("H1 2025 = Q1 + Q2 2025", got["H1 2025"], q1_25 + q2_25)
    check("H1 2025, Jun-2026 10-Q vs Jun-2025 10-Q", got["H1 2025"], col("0001594805-25-000073", "Six", "2025"))
    q3_25, m9_25 = col("0001594805-25-000089", "Three", "2025"), col("0001594805-25-000089", "Nine", "2025")
    check("9M 2025 = H1 2025 + Q3 2025", m9_25, got["H1 2025"] + q3_25)
    print(f"  NOTE FY2025 = H1 + H2: Q4 2025 is not disclosed on its own in the 10-K, so H2 can't be "
          f"checked against a reported figure. Implied Q4 = FY - 9M = {got['FY2025'] - m9_25:,.0f}; "
          f"implied H2 = {got['FY2025'] - got['H1 2025']:,.0f}.")

    print("\n== Same year reported in several annual filings")
    annual = {}
    for accn, table in tables.items():
        for group, year, raw in (table["columns"] if table else []):
            if group.startswith("Years ended"):
                annual.setdefault(year, []).append((float(raw.replace(",", "")) * table["scale"], accn))
    for year, vals in sorted(annual.items()):
        spread = max(v for v, _ in vals) - min(v for v, _ in vals)
        status = "consistent" if spread < 0.5 else f"DIFFER by {spread:,.3f}"
        print(f"  {year}: {status}  " + ", ".join(f"{v:,.3f} ({a})" for v, a in vals))
    if not ok:
        sys.exit("Sanity checks failed")


if __name__ == "__main__":
    main()
