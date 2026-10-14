# Model decisions log

Every judgment call in the model, with the reasoning. Feeds the memo.

## 1. Discount rate (WACC): 10.39%
*Decided: 2026-10-14*

| Input | Value | Source |
|---|---|---|
| Risk-free rate | 5.21% | Fed H.15, 10Y Treasury constant maturity, Oct 13 2026 |
| Market risk premium | 4.14% | Damodaran implied ERP, Sep 1 2026 |
| Raw beta | 2.62 | Yahoo Finance, 5Y monthly, Oct 14 2026 |
| Adjusted beta (Blume) | 2.09 | 0.67 × raw + 0.33 |
| Industry beta | 1.25 | Damodaran, US Software (System & Application), unlevered, corrected for cash, Jan 2026 |

| Version | Cost of equity |
|---|---|
| Raw beta | 16.06% |
| Adjusted beta | 13.84% |
| **Industry beta (base case)** | **10.39%** |

**Rationale (draft, rewrite in my own words):**
I use a WACC of 10.4%, equal to Shopify's cost of equity since it carries no debt after settling its convertible notes in November 2025. I estimate it with CAPM using a bottom-up software-industry beta of 1.25 (Damodaran) rather than Shopify's raw 5-year beta of 2.62, which is inflated by the 2021–23 drawdown and reflects a loss-making, logistics-heavy business that no longer exists. Because the beta choice alone moves the cost of equity from 10.4% to 16.1%, I test WACC from 8% to 14% in the sensitivity analysis, with the adjusted-beta case (13.8%) as the conservative view.

## 2. SBC treatment: subtract (base case)
*Decided: 2026-10-14*

- Reported FCF adds SBC back because it's non-cash, but SBC is still compensation, paid in shares that dilute existing owners.
- TTM: FCF $2,352M − SBC $482M = **$1,870M** (margin 14.1% vs 17.7% reported). SBC is ~20% of reported FCF.
- Forecast SBC at **4.0% of revenue**, held flat (FY24 4.8%, FY25 3.9%, TTM 3.6%).
- Because SBC is subtracted, the equity bridge uses the **current diluted share count**, with no extra future dilution.
- Buybacks are **not** subtracted as well; that would double-count, since buybacks partly offset SBC dilution.
- Toggle on Inputs (`subtract` / `ignore`) shows the value without the adjustment. "Ignore" overstates value unless dilution is modelled separately.

**Rationale (draft, rewrite in my own words):**
I treat stock-based compensation as a real cost. It's paid in shares rather than cash, but it dilutes existing shareholders just as surely, and reported free cash flow adds it back. Subtracting it at 4% of revenue lowers Shopify's starting FCF margin from 17.7% to 14.1%, and I show the unadjusted value as a sensitivity.

## 3. Non-operating assets and share count (equity bridge)
*Decided: 2026-10-14. Balance sheet as of Jun 30 2026 (Jun-2026 10-Q).*

| Item | USD m | Treatment |
|---|---|---|
| Cash & equivalents | 1,656 | 100% |
| Marketable securities (current + long-term) | 3,816 | 100% |
| **Cash & securities** | **5,472** | |
| Equity & other investments (Affirm, Global-E, Klaviyo, other) | 4,854 | 20% haircut |
| Flexport, equity method | 559 | 20% haircut (602 at Dec 31 2025) |
| Investments after haircut | 4,330 | (4,854 + 559) × 80% |
| Debt | 0 | Convertible notes settled Nov 2025 |
| **Net non-operating assets** | **9,802** | Added to EV in the equity bridge |

- **Haircut 20%** on investments only, not on cash: tax on any gains when sold, a block discount on large public stakes, and valuation uncertainty on the private Flexport stake. Cash and Treasury-type securities count at full value.
- **Diluted shares 1,290.0m** = cover-page basic shares 1,286.6m (Jul 31 2026) + 3.4m option/RSU dilution (H1 2026 diluted weighted 1,302.6m − basic weighted 1,299.3m, treasury-stock method). No extra future dilution, since SBC is subtracted as a cost (§2).
- **Market cap $222.5B** ($172.50 × 1,290.0m) − net non-operating assets $9.8B = **implied enterprise value $212.7B**, what the market pays for the operating business.
- **Interest income:** TTM $301M pre-tax ("Interest income" on marketable securities: FY2025 331 + H1 2026 141 − H1 2025 171), **$226M after 25% tax = 12.1% of TTM FCF − SBC** ($1,870M). It flows through reported FCF, so counting it in FCF *and* adding the cash that earns it would double-count.
- **Recommendation: (b).** Interest is ≥ 5% of TTM FCF − SBC, so strip after-tax interest income out of the starting FCF margin in the DCF (~$226M, about 1.7 points of TTM revenue), and keep cash & securities in the bridge.

**Rationale (draft, rewrite in my own words):**
I add $9.8B of net non-operating assets to the value of the operating business: Shopify's $5.5B of cash and securities at full value, plus its $5.4B of strategic stakes (Affirm, Global-E, Klaviyo and Flexport) after a 20% haircut for tax, block discounts and the uncertain value of the private Flexport stake. Because reported free cash flow already includes about $226M a year of after-tax interest earned on that cash, I strip it out of the starting FCF margin so the cash isn't counted twice. Dividing by 1,290M diluted shares, which includes in-the-money options and RSUs, the $222.5B market cap implies the market is paying about $212.7B for the operating business.
