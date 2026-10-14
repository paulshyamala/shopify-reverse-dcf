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

## 3. Non-operating assets (cash, securities, equity investments, Flexport)
*TBD (step 5)*
