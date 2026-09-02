# TaxTrack Zim — Legal & Computational Assumptions Register

This register separates **confirmed ZIMRA rules** (cited to a source) from
**assumptions** the system makes where the rule is genuinely ambiguous,
unverified at line-item level, or simplified for the scope of this project.
It is intended to be copied into the methodology/limitations section of the
project report largely as-is.

## Confirmed rules (cited)

| Rule | Detail | Source |
|---|---|---|
| Standard VAT rate | 15.5%, effective 1 January 2026 (previously 15%) | Finance Act (No. 7) of 2025, amending the VAT Act [Chapter 23:12]; ZIMRA Public Notice 7 of 2026 |
| Zero-rated supplies | Includes basic foodstuffs, agricultural inputs, and exports (except un-beneficiated chrome, taxed at the standard rate) | ZIMRA, "Taxable and Exempt supplies" |
| Exempt supplies | No VAT charged; input tax on related purchases is not claimable | ZIMRA, "Taxable and Exempt supplies" |
| VAT is invoice-based | Input tax can only be claimed against a valid (fiscalised) tax invoice | ZIMRA, "Mechanics of VAT" |
| Fiscalisation requirement | Registered operators must fiscalise point-of-sale devices | SI 104 of 2010, SI 148 of 2016, SI 153 of 2016 |
| Import VAT documentation | Claimable against a customs bill of entry, not a tax invoice | ZIMRA guidance on imports |
| VAT categories & filing | Categories A/B (bi-monthly, offset months), C (monthly), D (special, Commissioner-approved); VAT7 due by the 25th of the month following the tax period | ZIMRA FAQ |
| Net position mechanics | Output tax − input tax; positive = payable, negative = refundable | ZIMRA, "Mechanics of VAT" |
| Minimum refund payout | Refunds under US$60 (or ZiG equivalent) are held as a credit rather than paid out immediately | ZIMRA, "Mechanics of VAT" |
| Local currency | Zimbabwe operates a multi-currency system; the official local currency is the ZiG (ZWG), alongside USD | ZIMRA public notices |

## Flagged assumptions (not independently verified line-by-line)

| Area | Assumption made | Why it's flagged | Where it's surfaced |
|---|---|---|---|
| First Schedule classification | The exact, current item-by-item split between zero-rated and exempt (as amended by SI 15 of 2024) is not verified against the full gazetted Schedule. Sample data uses illustrative categories only. | The Schedule is long, amended piecemeal, and a full line-by-line audit was out of scope for this project. | `engine/rules.py`, `FIRST_SCHEDULE_CLASSIFICATION_STATUS` |
| VAT registration threshold | Kept configurable; sources conflict between US$25,000/year and US$60,000/year. Not used in the return calculation itself — this app assumes the business is already VAT-registered. | Public sources disagree depending on publication date. | `engine/rules.py`, `REGISTRATION_THRESHOLD_USD_PER_YEAR_ASSUMPTION` |
| Un-beneficiated chrome rate | Assumed to move to 15.5% along with the general rate increase, by extrapolation rather than a separately confirmed gazette reference. | Not separately re-confirmed after the Jan 2026 rate change. | `engine/rules.py` |
| Rate-transition mechanic (Dec 2025 / Jan 2026) | The engine applies "the rate in force on the transaction date" to each transaction individually. ZIMRA's actual Category A combined-return mechanic for that period instead grosses down the value of supply so the correct 15.5% tax is computed within a single combined return. | The simplified per-transaction approach is easier to explain and defend live, and produces the same net result for transactions cleanly on one side of the boundary, but is not an exact replica of the official transitional computation. | `engine/rules.py` (`RATE_TRANSITION_WINDOW`), flagged per-transaction as a warning in the calculation trail |
| FX source for ZiG (ZWG) | Uses Frankfurter's aggregated rate rather than the RBZ's official published interbank rate. | A real filing should use the RBZ rate; Frankfurter was chosen for being free, keyless, and reliable for a student deployment. | `services/fx.py`, `ASSUMPTIONS.md` (this file) |
| FX fallback rates | If Frankfurter is unreachable, a static rate snapshot (`engine/rates_fallback.json`, dated) is used instead, and flagged in the calculation trail. | Prevents a live demo from breaking on a flaky connection, at the cost of using a potentially stale rate. | `services/fx.py`, `ui/pages/3_Calculation_Trail.py` |
| Adjustment amounts | Adjustment transactions require an explicit signed VAT amount (`vat_amount_override`); the engine does not attempt to derive bad-debt or credit-note amounts from an underlying invoice automatically. | Deriving these automatically would require linking adjustments to specific prior invoices, which is a reasonable v2 feature but out of scope here. | `engine/calculator.py`, `_line_vat()` |
| Currency conversion timing | Transactions are converted at the exchange rate in force on the transaction date (or the latest available/fallback rate if unavailable), not at the rate on the return filing date. | This is the more defensible accounting treatment, but ZIMRA guidance on the exact conversion date to use for VAT purposes was not independently confirmed. | `services/fx.py`, `engine/calculator.py` |
| Shona / Ndebele translations | Machine-assisted translations of the UI strings, not reviewed by a native-speaking translator. | For a course project demo this is a reasonable simplification, but production use would need native-speaker review. | `locales/sn.json`, `locales/nd.json` |

## Explicit simplifications (by design, not a ZIMRA ambiguity)

- The system assumes the filer is already VAT-registered; it does not model registration itself.
- Partial input tax apportionment for mixed taxable/exempt use is supported only via a manual `adjustment` transaction, not automatically pro-rated.
- The system does not model VAT withheld by an appointed withholding agent as a separate workflow beyond the generic `adjustment` mechanism.
- No integration with ZIMRA's TaRMS/e-filing system — the output is a summary and downloadable CSV, not a filed return.
