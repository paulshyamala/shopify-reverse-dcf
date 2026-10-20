# Valuation defence: every assumption justified

**Base case: $77.98 per share** vs **$172.50** market price (Oct 14 2026). FCFF DCF with Damodaran terminal rules (stable β = 1.0, moat spread 2%). Every number is either a **fact** (from filings) or a **judgment** (chosen, with the reason given). Dollar impacts come from re-running the model one input at a time.

## Part 0: What matters most

| Rank | Assumption | Base | Test | $ impact per share |
|---|---|---|---|---|
| 1 | SBC treatment | Cost | Treat as free | +20.96 |
| 2 | Terminal EBIT margin | 25% | 20% / 30% | −13.77 / +13.77 |
| 3 | Equity risk premium | 4.14% | 5.0% / 5.5% | −10.01 / −14.86 |
| 4 | Year-1 GMV growth | 29% | 25% / 33% | −9.71 / +11.10 |
| 5 | Risk-free rate | 5.21% | ±0.5 pt | +6.28 / −5.46 |
| 6 | Beta | 1.25 | 1.0 / 1.5 | +6.20 / −5.62 |
| 7 | Stable-period beta | 1.00 | 1.25 | −5.44 |
| 8 | Loan-book reinvestment | 20% | 0% / 15% / 25% | +5.40 / +1.35 / −1.35 |
| 9 | Year-10 GMV growth | 7% | 5% / 9% | −4.64 / +4.97 |
| 10 | Moat spread | 2% | 0% / 3% | −3.65 / +1.38 |
| 11 | Take-rate increase | +0.02 pt/yr | 0 / +0.03 | −3.63 / +1.82 |
| 12 | Terminal tax | 24% | 26.5% | −2.13 |
| 13 | Terminal growth | 3% | 2.5% / 3.5% | −1.06 / +1.21 |
| 14 | Investment haircut | 20% | 0% / 50% | +0.84 / −1.26 |
| 15 | Working capital | 4% | 2% / 6% | ±0.54 |

No single reasonable change gets near $172.50. Closing the $95 gap needs several optimistic choices stacked together (Part 9).

## Part 1: Framework decisions

**1.1 Intrinsic, not relative.** The project asks what the price implies about the business; a multiple assumes peers are priced correctly and can't test that. Sell-side targets are mostly multiples (e.g. Morgan Stanley: 25× EV/FCF, "in line with the LargeCap Software median"); Morningstar and Simply Wall St are intrinsic. Damodaran (Session 1): relative valuation assumes markets are right on average.

**1.2 Firm valuation (FCFF at WACC), then the equity bridge.** Shopify has $0 debt, $178M of leases and $9.6B of net non-operating assets; separating them shows the market pays $212.9B for the business alone. Damodaran (Sessions 2, 11): never mix routes; with no debt WACC = cost of equity.

**1.3 Ten-year, two-stage model.** Damodaran Rule 2 (Session 9): ~99% of growth firms have high-growth periods under 10 years. Morningstar uses 3 stages and ~20 years; McKinsey 10–15. The cap is on high growth, not advantage: terminal ROIC stays 2 points above the cost of capital forever. Twenty years of fading growth adds only ~$10 ($87.93). Matching Morningstar's $145 needs ~15% growth in years 11–20, ending at ~$289B of revenue (22× today); that alone reproduces ~$142.

**1.4 GMV × take rate.** Mirrors how Shopify earns money, separates market share from pricing, and enables the e-commerce reality check (Damodaran: every number translates a piece of the story).

**1.5 TTM to Jun 30 2026.** TTM = FY2025 + H1 2026 − H1 2025 (Damodaran Session 7: use trailing 12 months). The June 30 base vs Oct 14 price makes the value ~3% too low (conservative).

## Part 2: Starting data (facts)

| Item | Value | Source / check |
|---|---|---|
| TTM revenue | $13,269M | 10-K + 10-Q; FY2025 $11,556M matches press release |
| TTM GMV | $432,164M | KPI tables; FY2024–25 match exactly |
| TTM EBIT | $1,844M | Operating income (includes SBC and loan losses) |
| TTM reported FCF | $2,352M | OCF − capex; FY2025 $2,007M matches Shopify |
| TTM SBC | $482M | Cash flow statement |
| Cash + securities | $5,472M | Jun 30 2026 balance sheet |
| Equity investments / Flexport | $4,854M / $559M | Balance sheet |
| Debt | $0 (+ $178M operating leases) | Notes repaid Nov 2025 (~$1,043M cash); leases Jun-2026 10-Q |
| Diluted shares | 1,290.0M | 1,286.6M cover page + 3.4M dilution |
| Share price | $172.50 | NASDAQ close, Oct 14 2026 |

## Part 3: Discount rate (WACC 10.385%)

$$\text{WACC} = r_f + \beta \times \text{ERP} = 5.21\% + 1.25 \times 4.14\% = 10.385\%$$

- **Risk-free 5.21%:** Fed H.15, 10-year Treasury, Oct 13 2026; same currency, nominal, Damodaran's preferred maturity. Kroll uses the spot 20-year (~5.60%).
- **ERP 4.14%:** Damodaran implied ERP, Sep 2026 (forward-looking, Session 4). Kroll recommends 5.0% (Sep 2026) and the Fernandez practitioner survey averages 5.5% (2025). **Generous to Shopify**: those would cut value by $10 and $15.
- **Beta 1.25:** Damodaran US Software (System & Application), unlevered, corrected for cash. Shopify's regression beta of 2.62 is distorted by the 2021–23 crash and a business that no longer exists (Session 5). **Generous to Shopify**: raw beta gives a 16% cost of equity, Blume-adjusted 13.8%. Known simplification: software-only beta for a software + payments + lending company.
- **Debt weight 0%:** notes repaid Nov 2025; $178M of operating leases are subtracted in the equity bridge instead (Part 8).

| Source | Market rate (β = 1) | For β = 1.25 |
|---|---|---|
| **This model** | **9.35%** | **10.385%** |
| Kroll inputs | ~10.6% | ~11.85% |
| Fernandez survey | ~9.6% | ~11.0% |
| Morningstar (Shopify) | 9.0% cost of equity, 8.8% WACC | |

## Part 4: Operating forecast

- **Year-1 GMV growth 29%:** FY2025 +29.5%; H1 2026 +33% (partly FX: Q4 2025 31% reported vs 29% constant currency); Q3 guidance "low-thirties". Model CY2027 revenue ~$19.6B vs Street consensus ~$19.2B, so near-term growth matches the Street. Starting at 33% gives ~$89.
- **Year-10 GMV growth 7%, linear fade:** Fed long-run 2.0% real + 2.0% inflation ≈ 4% nominal; ~2× the economy at ~$2.2T of GMV. Model 10-year revenue CAGR ~18.5% vs TIKR ~20–22% and Morningstar's ~21% first stage.
- **Take rate 3.07% → 3.27%:** 2.63% (FY21) → 3.12% (H1 26), slowing; flat would cut $3.63, so slightly generous.
- **EBIT margin 13.9% → 25% (biggest judgment):** needs opex to fall from ~34% to ~23% of revenue. More optimistic than Morningstar (mid-teens GAAP by 2029) and PayPal (18.3% GAAP FY2025). The ~48% gross margin caps the ceiling.
- **Tax 19% → 24%:** effective 18.4% (FY25), 19.3% (H1 26); cash taxes $27M (FY22) → $347M (TTM). Damodaran: effective early, moving to marginal. Morningstar uses 26.5%; 24% is slightly generous (−$2.13 at 26.5%).

## Part 5: Reinvestment

- **Capex / D&A 0.2% each:** TTM $25M / $29M; asset-light, net to roughly zero.
- **Working capital 4% of new revenue:** FY2025 4.4%, H1 2026 4.1%.
- **Loan book 20% of new revenue:** Δ net loan book ÷ Δ revenue FY23 16.2%, FY24 22.4%, FY25 20.9%; book rose from 10% to 16.5% of revenue. Largest reinvestment (~23× capex), excluded from reported FCF because it sits in investing cash flow (and merchant cash advances moved there from April 2026). Damodaran: reinvestment defined broadly; the loans are current assets (non-cash working capital). Loan losses are in EBIT and lending income in revenue, so both cost and benefit count.

## Part 6: SBC is a real cost (+$20.96 if ignored)

TTM SBC $482M (3.6% of revenue). The model starts from EBIT (SBC already deducted), uses today's diluted shares (granted awards included), adds no future dilution, and does not also subtract buybacks. Paying $482M in shares is economically identical to selling $482M of shares and paying cash; only the latter shows in FCF. Correct treatments: expense it, or model future dilution. Ignoring both (reported FCF, adjusted metrics, multiples, automated DCFs) overstates value.

## Part 7: Terminal value (~67% of value)

- **Terminal growth 3%:** below Fed long-run nominal GDP (~4%) and the risk-free rate (Rule 1).
- **Stable beta 1.0 → stable WACC 9.35%:** Rule 4; generous to Shopify (β 1.25 would cut $5.44).
- **Stable ROIC = 9.35% + 2% = 11.35%; reinvestment = g / ROIC = 26.4%:** Rule 3, growth must be paid for. The old model implied 82% ROIC forever. A 2% moat (lower end of Damodaran's 2–3%) reflects switching costs and ecosystem effects, tempered by competition (Amazon, WooCommerce, BigCommerce/Wix, Stripe, AI shopping agents). Morningstar rates Shopify wide moat.

$$\text{FCFF}_{11} = \text{NOPAT}_{11}\left(1 - \frac{3\%}{11.35\%}\right) \qquad TV = \frac{\text{FCFF}_{11}}{9.35\% - 3\%}$$

## Part 8: Equity bridge

| Item | Value | Reason | Damodaran / others |
|---|---|---|---|
| Cash + securities | $5,472M at 100% | Face value | $1 ≈ $1 |
| Equity stakes (Affirm, Global-E, Klaviyo) | $4,854M at 80% | Tax on gains; block discount | Market value, no haircut (+$0.84): conservative |
| Flexport | $559M at 80% | Private; estimate | Book × industry P/B |
| Interest income | Excluded (below EBIT) | Cash added in the bridge | FAQ 10 |
| Debt | $0 + $178M leases | Notes repaid; all leases operating | Leases count as debt (−$0.14) |
| Diluted shares | 1,290.0M | Basic + treasury-method dilution | No extra dilution since SBC expensed |

## Part 9: Why $78 and not the other numbers

| Model | Value | What it assumes that this model doesn't |
|---|---|---|
| **This model** | **$77.98** | |
| Simply Wall St (Oct 2026) | ~$114 | Reported FCF (SBC added back, lending ignored), lower discount rate |
| Morningstar (Aug 2026) | $145 | 8.8% WACC; ~15% profit growth to year 20; higher FCF margin |
| Street targets (48 analysts) | ~$176 (low $130, high $210, 0 Sells) | Multiples on SBC-excluded figures; 12-month targets that track the price |
| Market price | $172.50 | ~30% GMV growth a year for 10 years |

| Step | Change | Value per share |
|---|---|---|
| | This model | $77.98 |
| 1 | Treat SBC as free | $98.94 |
| 2 | Ignore lending | $104.34 |
| 3 | 9% WACC (≈ Simply Wall St) | $118.94 |
| 4 | 30% terminal margin (≈ Morningstar) | $134.90 |
| 5 | GMV growth 33% → 9% (≈ market / Street) | $166.68 |

## Part 10: Generous vs conservative

| Generous to Shopify (raises value) | Conservative (lowers value) |
|---|---|
| ERP 4.14%, lowest current estimate | SBC as a cost (−$21 vs Street) |
| Beta 1.25 vs Shopify's own 2.62 | Lending as reinvestment (−$5) |
| 25% terminal margin, above Morningstar and PayPal | 10-year high-growth cap (vs Morningstar's 20) |
| Take rate keeps rising | 20% haircut on investments (−$0.84) |
| Stable beta 1.0 | June 30 base vs Oct 14 price (~−3%) |
| Terminal tax 24% vs 26.5% | Moat spread 2%, not 3% (−$1.38) |
| Year-10 growth ~2× GDP | |

On discount rate, margins and beta the model takes the Shopify-friendly option. The low value comes from three principled positions: SBC is a real cost, lending is real reinvestment, and fast growth doesn't last 20 years.

## Sources

- Morningstar equity report on Shopify (2025): https://invest.firstrade.com/ms/equity_reports/sr/2025/0P00015ZGZ_20250508_RT.pdf
- Morningstar note, FV $145 (Aug 2026): https://global.morningstar.com/en-ca/stocks/shopify-earnings-strong-results-guidance-command-higher-estimates
- MarketBeat SHOP price targets: https://www.marketbeat.com/stocks/NASDAQ/SHOP/price-target/
- Simply Wall St SHOP valuation: https://simplywall.st/stocks/us/software/nasdaq-shop/shopify/valuation
- Kroll 5.0% U.S. ERP (BVR, Sep 2026): https://www.bvresources.com/articles/bvwire/kroll-reaffirms-50-us-erp-sticks-with-treasury-risk-free-rate
- Fernandez 2025 survey (BVR): https://www.bvresources.com/articles/bvwire/global-fernandezs-survey-of-2025-risk-premiums-and-risk-free-rates
- Morgan Stanley price-target method (Benzinga): https://benzinga.com/z/35596976
- TIKR, 2027 consensus (Oct 2026): https://www.tikr.com/blog/shopify-stock-is-up-15-since-september-2025-heres-why-it-trades-at-a-lower-forward-p-e
- Shopify Q2 2026 results: https://www.shopify.com/news/shopify-q2-2026-financial-results
- PayPal Q4 2025 earnings release: https://s205.q4cdn.com/875401827/files/doc_financials/2025/q4/PYPL-4Q-25-Earnings-Release.pdf
- Fed long-run projections (Sep 2026): https://federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm
- Fed H.15: https://www.federalreserve.gov/releases/h15/
