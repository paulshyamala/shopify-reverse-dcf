# Model decisions log

Every judgment call in the model, with the reasoning. Feeds the memo.

## Summary of key decisions

**Discount rate: 10.4%.** Shopify has no debt, so its WACC equals its cost of equity. Using CAPM: 5.21% risk-free rate + 1.25 software-industry beta × 4.14% equity risk premium. I use an industry beta rather than Shopify's raw 2.62, which is inflated by the 2021–23 drawdown and reflects a loss-making business that no longer exists. Sensitivity analysis covers 8–14%.

**Stock-based compensation: treated as a real cost.** Employees are paid partly in shares, which dilutes existing owners, but reported free cash flow adds it back. I subtract it at 4% of revenue and use today's diluted share count, with no additional future dilution. Buybacks are not also subtracted, to avoid double-counting.

**Non-operating assets: +$9.8B.** Cash and marketable securities ($5.5B) at full value; strategic equity stakes and Flexport ($5.4B) at 80% to reflect tax on gains and limited liquidity. No debt. Equity value is divided by 1,290m diluted shares.

**Starting margin: 12.4%, not 17.7%.** Reported FCF margin is 17.7%. Subtracting SBC (3.6% of revenue) and after-tax interest on the cash pile (1.7%), which is already counted in the equity bridge, leaves 12.4% as the operating business's cash margin for owners.

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

**Rationale:**
I discount at 10.39%, which is simply Shopify's cost of equity, because the company has had no debt since settling its convertible notes in November 2025. I estimate it with CAPM (the risk-free rate plus beta, a stock's sensitivity to market swings, times the equity risk premium), using Damodaran's 1.25 beta for US software companies instead of Shopify's own 5-year beta of 2.62, which is distorted by the 2021–23 crash and by the loss-making, logistics-heavy business Shopify has since exited. The beta choice alone moves the cost of equity from 10.39% to 16.06%, so I test WACC from 8% to 14% in the sensitivity analysis and treat the adjusted-beta case (13.84%) as the conservative view.

## 2. SBC treatment: subtract (base case)
*Decided: 2026-10-14*

- Reported FCF adds SBC back because it's non-cash, but SBC is still compensation, paid in shares that dilute existing owners.
- TTM: FCF $2,352M − SBC $482M = **$1,870M** (margin 14.1% vs 17.7% reported). SBC is ~20% of reported FCF.
- Forecast SBC at **4.0% of revenue**, held flat (FY24 4.8%, FY25 3.9%, TTM 3.6%).
- Because SBC is subtracted, the equity bridge uses the **current diluted share count**, with no extra future dilution.
- Buybacks are **not** subtracted as well; that would double-count, since buybacks partly offset SBC dilution.
- Toggle on Inputs (`subtract` / `ignore`) shows the value without the adjustment. "Ignore" overstates value unless dilution is modelled separately.

**Rationale:**
I treat stock-based compensation (SBC: pay in shares rather than cash) as a real cost, because it dilutes existing owners even though reported free cash flow adds it back as a non-cash item. Over the last twelve months, subtracting SBC of $482M (3.6% of revenue) cuts the FCF margin from 17.7% to 14.1%, and I forecast SBC at 4.0% of revenue from here. The `ignore` setting on Inputs shows the value without this adjustment, which overstates value unless future dilution is modelled separately.

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

- **Haircut 20%** on investments only, not on cash: tax on any gains when sold, a block discount on large public stakes, and valuation uncertainty on the private Flexport stake. Cash and marketable debt securities count at full value.
- **Diluted shares 1,290.0m** = cover-page basic shares 1,286.6m (Jul 31 2026) + 3.4m option/RSU dilution (H1 2026 diluted weighted 1,302.6m − basic weighted 1,299.3m, treasury-stock method). No extra future dilution, since SBC is subtracted as a cost (§2).
- **Market cap $222.5B** ($172.50 × 1,290.0m) − net non-operating assets $9.8B = **implied enterprise value $212.7B**, what the market pays for the operating business.
- **Interest income:** TTM $301M pre-tax ("Interest income" on marketable securities: FY2025 331 + H1 2026 141 − H1 2025 171), **$226M after 25% tax = 12.1% of TTM FCF − SBC** ($1,870M). It flows through reported FCF, so counting it in FCF *and* adding the cash that earns it would double-count.
- **Adopted: (b).** Interest is ≥ 5% of TTM FCF − SBC, so after-tax interest income (~$226M, about 1.7 points of TTM revenue) is stripped out of the starting FCF margin (Inputs, "Starting operating FCF margin"; see §4), and cash & securities stay in the bridge.

**Rationale:**
I add $9.8B of net non-operating assets (what Shopify owns outside its operating business, less debt) to the value of the operations: $5.5B of cash and marketable securities at full value, plus $5.4B of stakes in Affirm, Global-E, Klaviyo, Flexport and others, counted at 80% ($4.3B) for tax on gains, block discounts and the hard-to-value private Flexport stake. Reported free cash flow already includes about $226M a year of after-tax interest on that cash, so I strip it out of the starting margin to avoid counting the cash twice. At $172.50 a share and 1,290.0M diluted shares (including in-the-money options and RSUs), the $222.5B market cap means investors are paying about $212.7B for the operating business, its implied enterprise value.

## 4. Starting point: TTM to Jun 30 2026
*Decided: 2026-10-14*

| | $M | % of revenue |
|---|---|---|
| Revenue | 13,269 | |
| Reported FCF | 2,352 | 17.7% |
| − SBC | 482 | 3.6% |
| − After-tax interest income | 226 | 1.7% |
| **Operating FCF (owners' cash, ex-interest)** | **1,644** | **12.4%** |

**Rationale:**
I start the forecast from the twelve months to Jun 30 2026 (TTM), the most recent full year of results. The reported 17.7% free cash flow margin overstates what the operating business earns for owners: SBC is a real cost paid in shares, and the interest earned on Shopify's ~$5.5B of cash is already valued separately in the equity bridge. Stripping both out leaves a 12.4% operating FCF margin, which is where the DCF starts before ramping to the terminal margin.
