# Model decisions log

Every judgment call in the model, with the reasoning. Feeds the memo.

## Summary of key decisions

**Discount rate: 10.4% for years 1–10, 9.35% after.** Shopify has no debt, so its WACC equals its cost of equity. Using CAPM: 5.21% risk-free rate + 1.25 software-industry beta × 4.14% equity risk premium. I use an industry beta rather than Shopify's raw 2.62, which is inflated by the 2021–23 drawdown and reflects a loss-making business that no longer exists. After year 10 the beta moves to 1.00 (9.35%, Damodaran Rule 4). Sensitivity analysis covers 8–12% (stable rate moved in step).

**Stock-based compensation: treated as a real cost.** Employees are paid partly in shares, which dilutes existing owners, but reported free cash flow adds it back. I subtract it at 4% of revenue and use today's diluted share count, with no additional future dilution. Buybacks are not also subtracted, to avoid double-counting.

**Non-operating assets: +$9.6B.** Cash and marketable securities ($5.5B) at full value; strategic equity stakes and Flexport (\$5.4B) at 80% to reflect tax on gains and limited liquidity. No debt, but \$178M of operating lease liabilities are subtracted as debt. Equity value is divided by 1,290m diluted shares.

**Cash flow: FCFF built from EBIT, with the loan book as reinvestment.** The DCF values free cash flow to the firm: EBIT (which already deducts SBC and Shopify Capital loan losses, and excludes interest income) after a tax rate rising from 19% to 24%, plus D\&A, minus capex, working capital and growth in the Shopify Capital loan book. The loan book grows by 20% of each revenue increase, the largest reinvestment in the model and one that reported free cash flow leaves out, because loans sit in investing cash flow. The reported 17.7% FCF margin and the adjusted 12.4% margin are kept for reference only.

**Terminal value: growth after year 10 must be paid for.** After year 10 Shopify is treated as a mature firm (Damodaran Rules 3 & 4): beta 1.00, a 9.35% cost of capital, and a return on new capital 2 points above it (11.35%), so 26.4% of NOPAT is reinvested to grow at 3% a year.

**Result: \$77.98 per share**, against a \$172.50 price (−55%). The price implies about 30.5% GMV growth every year for ten years; even the bull scenario (\$129.04) and Street-style assumptions stacked together (\$166.68) stay below it.

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

*Updated 2026-10-20 (§12): \$178M of lease liabilities are now subtracted as debt, so net non-operating assets are \$9,624M (table below shows the original \$9,802M).*

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

* **Market cap $222.5B** ($172.50 × 1,290.0m) − net non-operating assets $9.8B = **implied enterprise value $212.7B**, what the market pays for the operating business.

* **Interest income:** TTM $301M pre-tax ("Interest income" on marketable securities: FY2025 331 + H1 2026 141 − H1 2025 171), **$226M after 25% tax = 12.1% of TTM FCF − SBC** (\$1,870M). It flows through reported FCF, so counting it in FCF *and* adding the cash that earns it would double-count.

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

GMV growth: Year-1 GMV growth of 29% is set slightly below H1 2026's 33% (which includes FX tailwinds) and in line with FY2025's 29.5%. Starting at 33% raises the value to \~\$89, still far below the price (was \~\$96 before the terminal-value change in §10).

**Rationale:**
I build free cash flow to the firm from EBIT rather than starting from reported free cash flow, because EBIT already charges the two costs reported FCF adds back, stock-based compensation and Shopify Capital loan losses, and it leaves out interest income, which the cash is credited for separately in the equity bridge. Reported FCF also omits Shopify's largest reinvestment: loans to merchants sit in investing cash flow, yet the loan book has been growing by about 20 cents for every extra dollar of revenue. Modelling that reinvestment explicitly, alongside working capital, capex and a tax rate that rises as tax shields run out, gives a cash flow that reflects what the business actually leaves for its owners.

## 6. Base-case result

*Model as of 2026-10-20: FCFF build (§5), Damodaran terminal rules (§10), leases (§12); share price \$172.50 (Oct 14 2026)*

| <br /> | Value |
|---|---|
| Sum of PV of FCFF, years 1–10 | \$29.6B |
| PV of terminal value | \$61.3B |
| **Enterprise value** | **\$91.0B** |
| + Net non-operating assets (after \$178M leases) | \$9.6B |
| Equity value | \$100.6B |
| ÷ Diluted shares | 1,290.0m |
| **Value per share** | **\$77.98** |
| Terminal value % of EV | 67.4% |
| Terminal value / year-10 EBIT | 9.1× |
| vs share price \$172.50 | -55% |
| vs Morningstar fair value \$145 (Aug 2026) | -46% |
| Model EV ÷ market-implied EV (\$212.9B) | 0.43× |

At a 10.39% WACC for years 1–10, a 9.35% stable WACC after year 10, 3% terminal growth and a 25% terminal EBIT margin, the base case is worth about \$78 a share, 55% below the current price and 46% below Morningstar's \$145. The market is pricing in more than twice the operating value this forecast supports. Two of the most sensitive inputs: a 30% terminal EBIT margin lifts the value to about \$92, and ignoring SBC as a cost lifts it to about \$99.

*Superseded: \$84.10 per share (EV \$98.7B, TV 70.0% of EV, 2026-10-15), before the terminal-value change (§10: \$78.12) and leases (§12: −\$0.14).*

## 7. Reverse DCF

*Solved 2026-10-20 (scripts/reverse.py); share price \$172.50*

Method: constant GMV growth for 10 years, all other assumptions at base case (for (c) and (d), the single input named is solved instead, with everything else at base case).

| What the \$172.50 price implies | Value | Base case |
|---|---|---|
| (a) Constant GMV growth, all 10 years | 30.5% | 29% → 7% fade |
| (b) Constant GMV growth equivalent to the base case (\$77.98) | 18.6% | <br /> |
| (c) Terminal (year-10) EBIT margin, base growth fade | 59.3% | 25.0% |
| (d) Year-1 GMV growth, fading linearly to 7% by year 10 | 53.1% | 29.0% |

Details at (a):

| <br /> | Value |
|---|---|
| Year-10 GMV | \$6.17T (14.3× TTM GMV of \$432B) |
| Year-10 revenue | \$201.7B (15.2× TTM revenue of \$13.3B) |
| Year-10 FCFF | \$26.8B |

* The price needs 30.5% GMV growth every year for ten years, 11.9 points a year more than the 18.6% constant rate equivalent to the base-case fade. That is today's pace (FY2025 29.5%, H1 2026 33.0%) sustained for a decade with no slowdown.

* Holding the growth fade, the price instead needs a 59.3% terminal EBIT margin, about 3.2 times PayPal's 18.3% GAAP operating margin (FY2025).

*Superseded (2026-10-18, before §10 and §12): (a) 29.1%, (b) 18.5%, (c) 53.8%, (d) 50.5%; year-10 GMV \$5.55T.*

## 8. Sensitivity

*Generated 2026-10-20 (scripts/sensitivity.py); share price \$172.50. Implied growth = the constant GMV growth for 10 years that makes value per share equal the price; all other assumptions at base case. Each WACC row moves the stable WACC by the same amount (base gap 1.035 points).*

**Grid 1: implied constant GMV growth, WACC × terminal EBIT margin**

| WACC ↓ / Terminal EBIT margin → | 20.0% | 22.5% | 25.0% (base) | 27.5% | 30.0% |
|---|---|---|---|---|---|
| 8.0% | 26.5% | 24.9% | 23.4% | 22.1% | 21.0% |
| 9.0% | 29.8% | 28.1% | 26.6% | 25.2% | 24.0% |
| 10.0% | 32.8% | 31.0% | 29.4% | 28.0% | 26.8% |
| **10.39% (base)** | 33.8% | 32.0% | **30.5%** | 29.0% | 27.8% |
| 11.0% | 35.5% | 33.7% | 32.1% | 30.6% | 29.3% |
| 12.0% | 38.1% | 36.2% | 34.6% | 33.1% | 31.7% |

**Grid 2: implied constant GMV growth, terminal growth × SBC treatment**

| Terminal growth ↓ / SBC → | subtract (base) | ignore |
|---|---|---|
| 2.0% | 30.9% | 27.4% |
| 2.5% | 30.7% | 27.1% |
| 3.0% (base) | **30.5%** | 26.7% |
| 3.5% | 30.2% | 26.3% |
| 4.0% | 29.8% | 25.8% |

**Grid 3: value per share (forward DCF, base growth fade), with upside / (downside) vs \$172.50**

| WACC ↓ / Terminal EBIT margin → | 20.0% | 22.5% | 25.0% (base) | 27.5% | 30.0% |
|---|---|---|---|---|---|
| 8.0% | \$98 (-43%) | \$109 (-37%) | \$120 (-31%) | \$131 (-24%) | \$142 (-18%) |
| 9.0% | \$80 (-53%) | \$89 (-48%) | \$98 (-43%) | \$107 (-38%) | \$116 (-33%) |
| 10.0% | \$68 (-61%) | \$75 (-56%) | \$83 (-52%) | \$90 (-48%) | \$97 (-44%) |
| **10.39% (base)** | \$64 (-63%) | \$71 (-59%) | **\$78 (-55%)** | \$85 (-51%) | \$92 (-47%) |
| 11.0% | \$59 (-66%) | \$65 (-62%) | \$71 (-59%) | \$78 (-55%) | \$84 (-51%) |
| 12.0% | \$52 (-70%) | \$57 (-67%) | \$63 (-64%) | \$68 (-61%) | \$73 (-58%) |

* WACC moves the answer most: from 8% to 12% (at a 25% terminal margin) the implied growth rises from 23.4% to 34.6%, 11.1 points, against 6.1 points across the whole 20–30% margin range, 1.1 points for terminal growth (2–4%, now small because growth after year 10 must be paid for) and 3.7 points for ignoring SBC.
* No cell brings implied growth below 20%: the lowest is 21.0% (8% WACC, 30% terminal margin), against a base-case-equivalent 18.6%.
* No cell in the forward DCF reaches the price: the best case (8% WACC, 30% margin) is worth \$142, 18% below \$172.50, and at the base 10.39% WACC the range is \$64–\$92.

*Superseded (2026-10-18, before §10 and §12): Grid 1 base 29.1%, Grid 3 base \$84.10, best Grid 3 cell \$158.*

## 9. Scenarios

*Generated 2026-10-20 (scripts/scenarios.py); share price \$172.50. Each scenario changes only the inputs below; everything else stays at base case. Stable beta is 1.00 in all three (stable WACC 9.35%); the WACC row is the high-growth (years 1–10) rate.*

| Input | Bear | Base | Bull | Rationale |
|---|---|---|---|---|
| GMV growth, year 1 | 25.0% | 29.0% | 33.0% | Bear: fast slowdown (Amazon, marketplaces, AI shopping agents). Bull: H1 2026's 33% pace holds longer. |
| GMV growth, year 10 | 5.0% | 7.0% | 9.0% | As above |
| Take rate increase per year | 0.00% | 0.02% | 0.03% | Bear: payments pricing pressure. Bull: more payments, ads and B2B. |
| Terminal EBIT margin (year 10) | 20.0% | 25.0% | 30.0% | Bear ≈ PayPal FY2025 GAAP 18.3%. Bull: mature-software scale. |
| Loan book % of revenue increase | 22.0% | 20.0% | 18.0% | Bear: lending needs more capital. Bull: more capital-efficient. |
| WACC | 11.50% | 10.39% | 9.50% | Bear sits between the industry-beta (10.4%) and adjusted-beta (13.8%) cost of equity. Bull: lower risk premium. |
| Terminal growth rate | 2.5% | 3.0% | 3.5% | All below ~4% long-run nominal GDP (Fed SEP). |
| Moat spread over stable WACC | 0.0% | 2.0% | 3.0% | Bear: no excess return after year 10 (ROIC = WACC). Bull: upper end of Damodaran's 2–3% for moat firms. |

| Output | Bear | Base | Bull |
|---|---|---|---|
| Value per share | **\$45.15** | **\$77.98** | **\$129.04** |
| Upside / (downside) vs price | -73.8% | -54.8% | -25.2% |
| Enterprise value | \$48.6B | \$91.0B | \$156.8B |
| Equity value | \$58.2B | \$100.6B | \$166.5B |
| PV of terminal value % of EV | 61.0% | 67.4% | 71.4% |
| Year-10 GMV | \$1.72T | \$2.22T | \$2.85T |
| Year-10 revenue | \$52.9B | \$72.7B | \$96.0B |
| Year-10 FCFF | \$7.4B | \$12.6B | \$20.0B |
| TV / year-10 EBIT | 8.3× | 9.1× | 9.6× |

**Probability-weighted value (illustrative, bear 25% / base 50% / bull 25%): \$82.54 per share**, -52% vs the price.

* Even the bull case, which keeps GMV growth near today's pace for longer, adds payments and ads take rate, reaches a 30% EBIT margin, earns a 3% moat spread and discounts at 9.5%, is worth \$129.04, 25% below the \$172.50 price.
* The market is pricing in more than the bull case: the price needs about 30% GMV growth every year for a decade (§7), against a bull case that fades from 33% to 9%.

*Superseded (2026-10-18, before §10 and §12): bear \$45.18, base \$84.10, bull \$156.63, weighted \$92.51.*

## 10. Terminal value: Damodaran Rules 3 & 4
*Decided: 2026-10-20*

**What changed.** Years 1–10 are unchanged. After year 10 the model now treats Shopify as a mature firm:

| | Before | After |
|---|---|---|
| Discount rate after year 10 | 10.385% (beta 1.25 forever) | **9.35%** (stable beta 1.00: 5.21% + 1.00 × 4.14%) |
| Year-11 reinvestment | 24% of the revenue increase (\$523M) | NOPAT × g / stable ROIC = **26.4%** of NOPAT (\$3,759M) |
| Return on new capital after year 10 | 82% implied, forever | **11.35%** (stable WACC + 2% moat spread) |
| Year-11 FCFF | \$13,698M | \$10,462M |
| Terminal value | \$185.5B | \$164.8B |
| PV of terminal value | \$69.1B | \$61.3B |
| Value per share | \$84.10 | \$78.12 (before leases; \$77.98 after, §12) |

**Why.** Rule 4: a mature firm's risk moves toward the market average, so the stable-period beta is 1.00 rather than Shopify's high-growth 1.25. Rule 3: growth must be paid for; the old terminal year reinvested only 3.7% of NOPAT to grow at 3%, which implies earning 82% on every new dollar forever. The new rule ties reinvestment to a return on capital: 3% growth at an 11.35% ROIC needs 26.4% of NOPAT reinvested.

**Why a 2% moat spread.** Damodaran's rule of thumb is that firms with durable advantages earn 2–3% above their cost of capital in stable growth. Shopify's switching costs and ecosystem (apps, payments, themes, Shop) justify a positive spread; competition from Amazon, WooCommerce, BigCommerce/Wix, Stripe and AI shopping agents argues for the lower end.

| Moat spread | 0% | 1% | 2% (base) | 3% | 5% |
|---|---|---|---|---|---|
| Value per share | \$74.33 | \$76.33 | **\$77.98** | \$79.37 | \$81.55 |

**ROIC sanity checks (DCF tab).** TTM reinvestment is 49% of NOPAT. The forecast's ROIC on new capital rises from 51% in year 1 to 79% in year 10 (sales-to-capital 4.17), then steps down to 11.35% in the stable period; FCFF falls from \$12,567M in year 10 to \$10,462M in year 11 (0.83×) as reinvestment rises to the stable rate.

**Rationale:**
I keep Shopify's high-growth assumptions for ten years but stop the model from assuming that a mature Shopify earns 82% on new capital forever with the risk of a high-growth software firm. After year 10 it carries market risk (beta 1.00, a 9.35% cost of capital) and earns 2 points above that on new investment, the lower end of what moat firms sustain, so a quarter of its profit must be reinvested to grow with the economy. This lowers the value from \$84.10 to \$78.12 a share, and the moat assumption matters relatively little: no moat at all gives \$74.33, a 5% spread \$81.55.

## 11. Comparison with professional estimates
*2026-10-20 (scripts/sensitivity.py; Sensitivity tab). External figures are as published, typed with sources.*

| Estimate | Value per share | Source / basis |
|---|---|---|
| **This model** | **\$77.98** | FCFF DCF, §5–§10, leases §12 |
| Street consensus target | \$175.89 | 48 analysts, low $130, high $210, 0 Sells; MarketBeat, Oct 2026 |
| Morningstar fair value | \$145.00 | Aug 2026; 2025 report: WACC 8.8%, CoE 9.0%, 3-stage to year 20, Stage II EBI growth 14.8%, mid-teens GAAP margin by 2029, tax 26.5%, wide moat |
| Simply Wall St DCF | \$113.77 | Oct 19 2026 |
| Share price | \$172.50 | NASDAQ close, Oct 14 2026 |

**Walk to Street assumptions (cumulative):**

| Step | Change | Value per share |
|---|---|---|
|  | This model | \$77.98 |
| 1 | Treat SBC as free (SBC ignore) | \$98.94 |
| 2 | Ignore lending (loan book % = 0) | \$104.34 |
| 3 | 9% WACC, stable 9% (≈ Simply Wall St) | \$118.94 |
| 4 | 30% terminal EBIT margin (≈ Morningstar) | \$134.90 |
| 5 | GMV growth 33% → 9% (≈ market / Street) | \$166.68 |

**Discount rates (cost of equity = risk-free + beta × ERP; this model's betas):**

| Source | Risk-free | ERP | Market rate (β = 1) | At β = 1.25 | Notes |
|---|---|---|---|---|---|
| This model | 5.21% | 4.14% | 9.35% | 10.39% | Inputs: 10Y Treasury (H.15) + Damodaran implied ERP |
| Kroll inputs | 5.60% | 5.00% | 10.60% | 11.85% | Kroll ERP 5.0% + spot 20-yr Treasury ~5.60% (H.15, Oct 13 2026) |
| Fernandez 2025 survey | 4.10% | 5.50% | 9.60% | 10.98% | Survey average ERP 5.5% + rf 4.1% |
| Morningstar (Shopify) | | | 9.0% (cost of equity) | 8.8% (WACC) | 9.0% cost of equity; 8.8% WACC (2025 equity report) |

**Longer growth runway (beyond the 10-year forecast):**

| Scenario | Assumption | Value per share | Final-year revenue |
|---|---|---|---|
| A, n = 5 | Fade 7% → 3% over years 11–15; ROIC and WACC fade to stable | \$82.78 | \$91B (year 15) |
| A, n = 10 | Fade 7% → 3% over years 11–20; ROIC and WACC fade to stable | \$87.93 | \$116B (year 20) |
| B (Morningstar-style) | Years 11–20 at 14.8%, high-growth WACC, 24% reinvestment | \$142.47 | \$289B (year 20) |
| B at 8.8% WACC | As B, with 8.8% for the high-growth and stable periods | \$186.22 | \$289B (year 20) |

**Rationale:**
This valuation sits below the Street mainly because of three choices: stock-based compensation is a real cost (about \$21 a share), Shopify Capital lending is reinvestment (about \$5), and fast growth is limited to ten years, after which new capital earns only 2 points above a market-risk cost of capital. Stacking Street-style assumptions (SBC treated as free, no lending reinvestment, a 9% discount rate, a 30% terminal margin and growth fading from 33% to 9%) takes the value from \$78 to about \$167, close to the \$172.50 price and the \$176 consensus. Morningstar's \$145 comes mostly from a longer runway at a lower discount rate: about 15% growth in years 11–20 gives \$142 at this model's WACC and \$186 at their 8.8%.

## 12. Leases
*Decided: 2026-10-20 (scripts/pull_bridge_inputs.py, scripts/add_leases.py)*

| Item | USD m | Source |
|---|---|---|
| Operating lease liabilities, current | 10 | us-gaap:OperatingLeaseLiabilityCurrent, Jun 30 2026, 10-Q 0001594805-26-000047 |
| Operating lease liabilities, non-current | 168 | us-gaap:OperatingLeaseLiabilityNoncurrent, Jun 30 2026, 10-Q 0001594805-26-000047 |
| **Lease liabilities** | **178** | All of Shopify's leases are operating leases (FY2025 10-K); no finance leases |

* Damodaran treats leases as debt, so the \$178M is subtracted in net non-operating assets alongside debt (\$0): \$9,802M → \$9,624M. EBIT is not adjusted for lease expense (a simplification; immaterial at this size).
* Impact: −\$0.14 per share (\$178M ÷ 1,290.0M shares), from \$78.12 to **\$77.98**. The market-implied EV rises from \$212.7B to \$212.9B.

## 13. Reality check
*2026-10-20 (scripts/reality_check.py, scripts/charts.py; Reality Check tab and charts/)*

**Sources.** eMarketer worldwide retail e-commerce, Forecast Feb 2025, as cited at shopify.com/blog/global-ecommerce-sales: \$6.007T (2024), \$6.419T (2025), \$6.880T (2026), \$7.375T (2027), \$7.886T (2028). Forrester global online retail, press release May 30 2024 (Business Wire): \$4.4T (2023) to \$6.8T (2028), 8.9% a year. Both checked against the cited pages on 2026-10-20.

**Extension method.** Each series is extended past its last year at its own growth rate to 2036: eMarketer at its 2025–28 CAGR (7.10%), Forrester at its stated 8.9% (2024–27 filled in from 2023 at the same rate). "Today" is the average of 2025 and 2026, because the TTM ends mid-2026 (eMarketer \$6.65T, Forrester \$5.45T); "year 10" is the average of 2035 and 2036 (\$13.20T and \$12.90T). Implied GMV = TTM GMV × (1 + the Reverse-tab implied growth)^10; scenario GMV links to the Scenarios tab.

| Case | Shopify GMV | Share, eMarketer | Share, Forrester |
|---|---|---|---|
| Today (TTM GMV, Jun 2026) | \$0.43T | 6.5% | 7.9% |
| Year 10: market-implied (30.5% constant growth) | \$6.17T | 46.7% | 47.8% |
| Year 10: bear scenario | \$1.72T | 13.0% | 13.3% |
| Year 10: base case | \$2.22T | 16.8% | 17.2% |
| Year 10: bull scenario | \$2.85T | 21.6% | 22.1% |
| Take-rate check (i): flat 3.07% take rate | \$6.57T | 49.8% | 50.9% |
| Take-rate check (ii): model take-rate path (3.27% in year 10) | \$6.17T | 46.7% | 47.8% |
| Take-rate check (iii): +0.10 pt per year (4.07% in year 10) | \$4.96T | 37.5% | 38.4% |

* The price needs Shopify's GMV to reach about 47% of global retail e-commerce in year 10, against 6.5% today and 17% in the base case. Even the bull scenario stops at 22%.
* A higher take rate softens this only partly: at +0.10 point a year (4.07% by year 10, a third above today's 3.07%) the price still needs 38% of the market; with a flat take rate it needs 50%.

**Caveats.**
* Shopify GMV includes offline (POS) and B2B sales, which retail e-commerce forecasts exclude, so every share here is overstated (an upper bound). FY2025 context: GMV \$378B, +29% (10-K); B2B GMV +96% for the full year; Q4 offline GMV +29%; Q4 Europe GMV +45% (35% in constant currency). The B2B, offline and Europe figures come from coverage of the Q4 2025 results (Digital Commerce 360, the earnings-call transcript, Zacks); the Feb 11 2026 release and the 10-K do not state them.
* Both market forecasts end in 2028; years to 2036 are a mechanical extension, not a forecast by either firm. Forrester's rounded endpoints imply 9.1% a year rather than the stated 8.9%.
* GMV is not revenue: the share describes merchant sales on Shopify, not Shopify's own sales.
