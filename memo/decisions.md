# Model decisions log

Every judgment call in the model, with the reasoning. Feeds the memo.

## Summary of key decisions

**Discount rate: 10.4%.** Shopify has no debt, so its WACC equals its cost of equity. Using CAPM: 5.21% risk-free rate + 1.25 software-industry beta × 4.14% equity risk premium. I use an industry beta rather than Shopify's raw 2.62, which is inflated by the 2021–23 drawdown and reflects a loss-making business that no longer exists. Sensitivity analysis covers 8–14%.

**Stock-based compensation: treated as a real cost.** Employees are paid partly in shares, which dilutes existing owners, but reported free cash flow adds it back. I subtract it at 4% of revenue and use today's diluted share count, with no additional future dilution. Buybacks are not also subtracted, to avoid double-counting.

\*\*Non-operating assets: +$9.8B.** Cash and marketable securities ($5.5B) at full value; strategic equity stakes and Flexport (\$5.4B) at 80% to reflect tax on gains and limited liquidity. No debt. Equity value is divided by 1,290m diluted shares.

**Cash flow: FCFF built from EBIT, with the loan book as reinvestment.** The DCF values free cash flow to the firm: EBIT (which already deducts SBC and Shopify Capital loan losses, and excludes interest income) after a tax rate rising from 19% to 24%, plus D\&A, minus capex, working capital and growth in the Shopify Capital loan book. The loan book grows by 20% of each revenue increase, the largest reinvestment in the model and one that reported free cash flow leaves out, because loans sit in investing cash flow. The reported 17.7% FCF margin and the adjusted 12.4% margin are kept for reference only.

## 1. Discount rate (WACC): 10.39%

*Decided: 2026-10-14*

| Input                 | Value | Source                                                                                 |
| --------------------- | ----- | -------------------------------------------------------------------------------------- |
| Risk-free rate        | 5.21% | Fed H.15, 10Y Treasury constant maturity, Oct 13 2026                                  |
| Market risk premium   | 4.14% | Damodaran implied ERP, Sep 1 2026                                                      |
| Raw beta              | 2.62  | Yahoo Finance, 5Y monthly, Oct 14 2026                                                 |
| Adjusted beta (Blume) | 2.09  | 0.67 × raw + 0.33                                                                      |
| Industry beta         | 1.25  | Damodaran, US Software (System & Application), unlevered, corrected for cash, Jan 2026 |

| Version                       | Cost of equity |
| ----------------------------- | -------------- |
| Raw beta                      | 16.06%         |
| Adjusted beta                 | 13.84%         |
| **Industry beta (base case)** | **10.39%**     |

**Rationale:**
I discount at 10.39%, which is simply Shopify's cost of equity, because the company has had no debt since settling its convertible notes in November 2025. I estimate it with CAPM (the risk-free rate plus beta, a stock's sensitivity to market swings, times the equity risk premium), using Damodaran's 1.25 beta for US software companies instead of Shopify's own 5-year beta of 2.62, which is distorted by the 2021–23 crash and by the loss-making, logistics-heavy business Shopify has since exited. The beta choice alone moves the cost of equity from 10.39% to 16.06%, so I test WACC from 8% to 14% in the sensitivity analysis and treat the adjusted-beta case (13.84%) as the conservative view.

## 2. SBC treatment: subtract (base case)

*Decided: 2026-10-14*

* Reported FCF adds SBC back because it's non-cash, but SBC is still compensation, paid in shares that dilute existing owners.

* TTM: FCF $2,352M − SBC $482M = **\$1,870M** (margin 14.1% vs 17.7% reported). SBC is \~20% of reported FCF.

* Forecast SBC at **4.0% of revenue**, held flat (FY24 4.8%, FY25 3.9%, TTM 3.6%).

* Because SBC is subtracted, the equity bridge uses the **current diluted share count**, with no extra future dilution.

* Buybacks are **not** subtracted as well; that would double-count, since buybacks partly offset SBC dilution.

* Toggle on Inputs (`subtract` / `ignore`) shows the value without the adjustment. "Ignore" overstates value unless dilution is modelled separately.

**Rationale:**
I treat stock-based compensation (SBC: pay in shares rather than cash) as a real cost, because it dilutes existing owners even though reported free cash flow adds it back as a non-cash item. Over the last twelve months, subtracting SBC of $482M (3.6% of revenue) cuts the FCF margin from 17.7% to 14.1%, and I forecast SBC at 4.0% of revenue from here. The `ignore` setting on Inputs shows the value without this adjustment, which overstates value unless future dilution is modelled separately.

## 3. Non-operating assets and share count (equity bridge)

*Decided: 2026-10-14. Balance sheet as of Jun 30 2026 (Jun-2026 10-Q).*

| Item                                                          | USD m     | Treatment                          |
| ------------------------------------------------------------- | --------- | ---------------------------------- |
| Cash & equivalents                                            | 1,656     | 100%                               |
| Marketable securities (current + long-term)                   | 3,816     | 100%                               |
| **Cash & securities**                                         | **5,472** | <br />                             |
| Equity & other investments (Affirm, Global-E, Klaviyo, other) | 4,854     | 20% haircut                        |
| Flexport, equity method                                       | 559       | 20% haircut (602 at Dec 31 2025)   |
| Investments after haircut                                     | 4,330     | (4,854 + 559) × 80%                |
| Debt                                                          | 0         | Convertible notes settled Nov 2025 |
| **Net non-operating assets**                                  | **9,802** | Added to EV in the equity bridge   |

* **Haircut 20%** on investments only, not on cash: tax on any gains when sold, a block discount on large public stakes, and valuation uncertainty on the private Flexport stake. Cash and marketable debt securities count at full value.

* **Diluted shares 1,290.0m** = cover-page basic shares 1,286.6m (Jul 31 2026) + 3.4m option/RSU dilution (H1 2026 diluted weighted 1,302.6m − basic weighted 1,299.3m, treasury-stock method). No extra future dilution, since SBC is subtracted as a cost (§2).

* **Market cap** $222.5B** ($172.50 × 1,290.0m) − net non-operating assets $9.8B = **implied enterprise value $212.7B, what the market pays for the operating business.

* **Interest income:** TTM $301M pre-tax ("Interest income" on marketable securities: FY2025 331 + H1 2026 141 − H1 2025 171), **$226M after 25% tax = 12.1% of TTM FCF − SBC\*\* (\$1,870M). It flows through reported FCF, so counting it in FCF *and* adding the cash that earns it would double-count.

* **Adopted: (b).** Interest is ≥ 5% of TTM FCF − SBC, so after-tax interest income (\~\$226M, about 1.7 points of TTM revenue) is stripped out of the starting FCF margin (Inputs, "Starting operating FCF margin"; see §4), and cash & securities stay in the bridge.

**Rationale:**
I add $9.8B of net non-operating assets (what Shopify owns outside its operating business, less debt) to the value of the operations: $5.5B of cash and marketable securities at full value, plus $5.4B of stakes in Affirm, Global-E, Klaviyo, Flexport and others, counted at 80% ($4.3B) for tax on gains, block discounts and the hard-to-value private Flexport stake. Reported free cash flow already includes about $226M a year of after-tax interest on that cash, so I strip it out of the starting margin to avoid counting the cash twice. At $172.50 a share and 1,290.0M diluted shares (including in-the-money options and RSUs), the $222.5B market cap means investors are paying about $212.7B for the operating business, its implied enterprise value.

## 4. Starting point: TTM to Jun 30 2026

*Decided: 2026-10-14. Superseded on 2026-10-15 by the FCFF build (§5); kept for reference.*

| <br />                                        | \$M       | % of revenue |
| --------------------------------------------- | --------- | ------------ |
| Revenue                                       | 13,269    | <br />       |
| Reported FCF                                  | 2,352     | 17.7%        |
| − SBC                                         | 482       | 3.6%         |
| − After-tax interest income                   | 226       | 1.7%         |
| **Operating FCF (owners' cash, ex-interest)** | **1,644** | **12.4%**    |

**Rationale:**
I start the forecast from the twelve months to Jun 30 2026 (TTM), the most recent full year of results. The reported 17.7% free cash flow margin overstates what the operating business earns for owners: SBC is a real cost paid in shares, and the interest earned on Shopify's \~\$5.5B of cash is already valued separately in the equity bridge. Stripping both out leaves a 12.4% operating FCF margin, which is where the DCF starts before ramping to the terminal margin.

## 5. Forecast assumptions (FCFF build)

*Decided: 2026-10-15*

FCFF = EBIT × (1 − tax rate) + D&A − capex − working capital investment − loan book investment (+ SBC only if the SBC toggle is set to `ignore`). Ten forecast years (Jul 2026–Jun 2036) plus a terminal year; all assumptions live on Inputs, "DCF assumptions".

| Assumption                            | Value   | Basis / source                                                                |
| ------------------------------------- | ------- | ----------------------------------------------------------------------------- |
| TTM GMV                               | 432,164 | Historicals, TTM Jun-26                                                       |
| TTM take rate                         | 3.07%   | Starting revenue 13,269 / TTM GMV                                             |
| TTM EBIT                              | 1,844   | Historicals operating income, TTM Jun-26                                      |
| TTM EBIT margin                       | 13.9%   | TTM EBIT / starting revenue                                                   |
| GMV growth, year 1                    | 29.0%   | H1 2026 GMV +33%; Q3 2026 revenue guidance low-30s                            |
| GMV growth, year 10                   | 7.0%    | \~2× long-run nominal GDP; linear fade from year 1                            |
| Take rate increase per year           | 0.02%   | History: 2.63% (FY21) → 3.12% (H1 26)                                         |
| Terminal EBIT margin (year 10)        | 25.0%   | Linear ramp from TTM. Opex \~34% → \~23% of revenue; PayPal GAAP 18.3% (FY25) |
| Tax rate, year 1                      | 19.0%   | Effective rate: FY25 18.4%, H1 26 19.3%                                       |
| Tax rate, year 10                     | 24.0%   | Rises as loss carryforwards/credits run out; cash taxes 27 → 347 (FY22 → TTM) |
| D\&A % of revenue                     | 0.2%    | TTM 29 / 13,269                                                               |
| Capex % of revenue                    | 0.2%    | TTM 25 / 13,269                                                               |
| Working capital % of revenue increase | 4.0%    | FY25 4.4%, H1 26 4.1%                                                         |
| Loan book % of revenue increase       | 20.0%   | Δ net loan book ÷ Δ revenue: FY23 16.2%, FY24 22.4%, FY25 20.9%               |
| Terminal growth rate                  | 3.0%    | Below Fed long-run nominal GDP (\~4%: 2.0% real + 2.0% PCE, SEP Sep 2026)     |

GMV growth: Year-1 GMV growth of 29% is set slightly below H1 2026's 33% (which includes FX tailwinds) and in line with FY2025's 29.5%. Starting at 33% raises the value to \~\$96, still far below the price.

**Rationale:**
I build free cash flow to the firm from EBIT rather than starting from reported free cash flow, because EBIT already charges the two costs reported FCF adds back, stock-based compensation and Shopify Capital loan losses, and it leaves out interest income, which the cash is credited for separately in the equity bridge. Reported FCF also omits Shopify's largest reinvestment: loans to merchants sit in investing cash flow, yet the loan book has been growing by about 20 cents for every extra dollar of revenue. Modelling that reinvestment explicitly, alongside working capital, capex and a tax rate that rises as tax shields run out, gives a cash flow that reflects what the business actually leaves for its owners.

## 6. Base-case result

*Model as of 2026-10-15; share price \$172.50 (Oct 14 2026)*

| <br />                                     | Value       |
| ------------------------------------------ | ----------- |
| Sum of PV of FCFF, years 1–10              | \$29.6B     |
| PV of terminal value                       | \$69.1B     |
| **Enterprise value**                       | **\$98.7B** |
| + Net non-operating assets                 | \$9.8B      |
| Equity value                               | \$108.5B    |
| ÷ Diluted shares                           | 1,290.0m    |
| **Value per share**                        | **\$84.10** |
| Terminal value % of EV                     | 70.0%       |
| Terminal value / year-10 EBIT              | 10.2×       |
| vs share price \$172.50                    | −51%        |
| vs Morningstar fair value \$145 (Aug 2026) | −42%        |
| Model EV ÷ market-implied EV (\$212.7B)    | 0.46×       |

At a 10.39% WACC, 3% terminal growth and a 25% terminal EBIT margin, the base case is worth about $84 a share, roughly half the current price and 42% below Morningstar's $145. The market is pricing in about twice the operating value this forecast supports, so the reverse DCF (what growth and margins justify $172.50) is the next step. Two of the most sensitive inputs: a 30% terminal EBIT margin lifts the value to about $99, and ignoring SBC as a cost lifts it to about \$103.

## 7. Reverse DCF

*Solved 2026-10-18 (scripts/reverse.py); share price \$172.50*

Method: constant GMV growth for 10 years, all other assumptions at base case (for (c) and (d), the single input named is solved instead, with everything else at base case).

| What the \$172.50 price implies                               | Value | Base case     |
| ------------------------------------------------------------- | ----- | ------------- |
| (a) Constant GMV growth, all 10 years                         | 29.1% | 29% → 7% fade |
| (b) Constant GMV growth equivalent to the base case (\$84.10) | 18.5% | <br />        |
| (c) Terminal (year-10) EBIT margin, base growth fade          | 53.8% | 25.0%         |
| (d) Year-1 GMV growth, fading linearly to 7% by year 10       | 50.5% | 29.0%         |

Details at (a):

| <br />          | Value                                 |
| --------------- | ------------------------------------- |
| Year-10 GMV     | $5.55T (12.8× TTM GMV of $432B)       |
| Year-10 revenue | $181.6B (13.7× TTM revenue of $13.3B) |
| Year-10 FCFF    | \$24.5B                               |

* The price needs 29.1% GMV growth every year for ten years, 10.6 points a year more than the 18.5% constant rate equivalent to the base-case fade. That is roughly today's pace (FY2025 29.5%, H1 2026 33.0%) sustained for a decade with no slowdown.

* Holding the growth fade, the price instead needs a 53.8% terminal EBIT margin, about three times PayPal's 18.3% GAAP operating margin (FY2025).

## 8. Sensitivity

*Generated 2026-10-18 (scripts/sensitivity.py); share price \$172.50. Implied growth = the constant GMV growth for 10 years that makes value per share equal the price; all other assumptions at base case.*

**Grid 1: implied constant GMV growth, WACC × terminal EBIT margin**

| WACC ↓ / Terminal EBIT margin → | 20.0% | 22.5% | 25.0% (base) | 27.5% | 30.0% |
| ------------------------------- | ----- | ----- | ------------ | ----- | ----- |
| 8.0%                            | 25.0% | 23.3% | 21.9%        | 20.6% | 19.4% |
| 9.0%                            | 28.3% | 26.6% | 25.1%        | 23.7% | 22.5% |
| 10.0%                           | 31.4% | 29.6% | 28.0%        | 26.6% | 25.4% |
| **10.39% (base)**               | 32.5% | 30.7% | **29.1%**    | 27.7% | 26.4% |
| 11.0%                           | 34.3% | 32.4% | 30.8%        | 29.3% | 28.0% |
| 12.0%                           | 37.0% | 35.0% | 33.3%        | 31.8% | 30.5% |

**Grid 2: implied constant GMV growth, terminal growth × SBC treatment**

| Terminal growth ↓ / SBC → | subtract (base) | ignore |
| ------------------------- | --------------- | ------ |
| 2.0%                      | 30.5%           | 27.4%  |
| 2.5%                      | 29.8%           | 26.7%  |
| 3.0% (base)               | **29.1%**       | 26.0%  |
| 3.5%                      | 28.3%           | 25.3%  |
| 4.0%                      | 27.5%           | 24.4%  |

**Grid 3: value per share (forward DCF, base growth fade), with upside / (downside) vs \$172.50**

| WACC ↓ / Terminal EBIT margin → | 20.0%        | 22.5%        | 25.0% (base)    | 27.5%        | 30.0%        |
| ------------------------------- | ------------ | ------------ | --------------- | ------------ | ------------ |
| 8.0%                            | \$107 (-38%) | \$120 (-30%) | \$133 (-23%)    | \$145 (-16%) | \$158 (-8%)  |
| 9.0%                            | \$87 (-49%)  | \$97 (-44%)  | \$107 (-38%)    | \$117 (-32%) | \$128 (-26%) |
| 10.0%                           | \$73 (-58%)  | \$81 (-53%)  | \$90 (-48%)     | \$98 (-43%)  | \$106 (-38%) |
| **10.39% (base)**               | \$69 (-60%)  | \$76 (-56%)  | **\$84 (-51%)** | \$92 (-47%)  | \$99 (-42%)  |
| 11.0%                           | \$63 (-64%)  | \$70 (-60%)  | \$76 (-56%)     | \$83 (-52%)  | \$90 (-48%)  |
| 12.0%                           | \$55 (-68%)  | \$61 (-65%)  | \$66 (-61%)     | \$72 (-58%)  | \$78 (-55%)  |

* WACC moves the answer most: from 8% to 12% (at a 25% terminal margin) the implied growth rises from 21.9% to 33.3%, 11.4 points, against 6.1 points across the whole 20–30% margin range and about 3 points each for terminal growth (2–4%) or ignoring SBC.

* Only the most optimistic corner gets implied growth below 20%: an 8% WACC with a 30% terminal margin needs 19.4%. Every other cell needs 20.6% or more, against a base-case-equivalent 18.5%.

* No cell in the forward DCF reaches the price: the best case (8% WACC, 30% margin) is worth \$158, 8% below \$172.50, and at the base 10.39% WACC the range is \$69–\$99.

## 9. Scenarios

*Generated 2026-10-18 (scripts/scenarios.py); share price \$172.50. Each scenario changes only the seven inputs below; everything else stays at base case.*

| Input                           | Bear   | Base   | Bull  | Rationale                                                                                                       |
| ------------------------------- | ------ | ------ | ----- | --------------------------------------------------------------------------------------------------------------- |
| GMV growth, year 1              | 25.0%  | 29.0%  | 33.0% | Bear: fast slowdown (Amazon, marketplaces, AI shopping agents). Bull: H1 2026's 33% pace holds longer.          |
| GMV growth, year 10             | 5.0%   | 7.0%   | 9.0%  | As above                                                                                                        |
| Take rate increase per year     | 0.00%  | 0.02%  | 0.03% | Bear: payments pricing pressure. Bull: more payments, ads and B2B.                                              |
| Terminal EBIT margin (year 10)  | 20.0%  | 25.0%  | 30.0% | Bear ≈ PayPal FY2025 GAAP 18.3%. Bull: mature-software scale.                                                   |
| Loan book % of revenue increase | 22.0%  | 20.0%  | 18.0% | Bear: lending needs more capital. Bull: more capital-efficient.                                                 |
| WACC                            | 11.50% | 10.39% | 9.50% | Bear sits between the industry-beta (10.4%) and adjusted-beta (13.8%) cost of equity. Bull: lower risk premium. |
| Terminal growth rate            | 2.5%   | 3.0%   | 3.5%  | All below \~4% long-run nominal GDP (Fed SEP).                                                                  |

| Output                       | Bear        | Base        | Bull         |
| ---------------------------- | ----------- | ----------- | ------------ |
| Value per share              | **\$45.18** | **\$84.10** | **\$156.63** |
| Upside / (downside) vs price | -73.8%      | -51.2%      | -9.2%        |
| Enterprise value             | \$48.5B     | \$98.7B     | \$192.3B     |
| Equity value                 | \$58.3B     | \$108.5B    | \$202.1B     |
| PV of terminal value % of EV | 60.9%       | 70.0%       | 76.7%        |
| Year-10 GMV                  | \$1.72T     | \$2.22T     | \$2.85T      |
| Year-10 revenue              | \$52.9B     | \$72.7B     | \$96.0B      |
| Year-10 FCFF                 | \$7.4B      | \$12.6B     | \$20.0B      |
| TV / year-10 EBIT            | 8.3×        | 10.2×       | 12.7×        |

**Probability-weighted value (illustrative, bear 25% / base 50% / bull 25%): \$92.51 per share**, -46% vs the price.

* Even the bull case, which keeps GMV growth near today's pace for longer, adds payments and ads take rate, reaches a 30% EBIT margin and discounts at 9.5%, is worth \$156.63, 9% below the \$172.50 price.

* The market is pricing in more than the bull case: the price needs roughly 29% GMV growth every year for a decade (§7), against a bull case that fades from 33% to 9%.
