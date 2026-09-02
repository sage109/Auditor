# TaxTrack Zim (TTZ)

Automated Zimbabwe VAT return calculation from accounting transaction data, built
as a university course project. TaxTrack Zim classifies transactions (standard-rated,
zero-rated, exempt, imported, adjustments), computes output tax, input tax, and the
net VAT payable/refundable position, and produces an auditable, line-by-line
calculation trail — all per current ZIMRA rules (see [`ASSUMPTIONS.md`](ASSUMPTIONS.md)
for exactly which rules are confirmed vs. assumed).

> This project uses entirely simulated, anonymised sample data. No real taxpayer
> data is included anywhere in this repository.

## Features

- **Calculation engine** independent of the UI — plain Python, zero third-party
  dependencies, fully unit tested (`engine/`)
- **Full audit trail**: every output/input tax figure traces back to the source
  transaction(s) that produced it, including which exchange rate was used and why
- **Multi-currency**: transactions can be entered in USD, ZWG (ZiG), ZAR, EUR, or
  GBP; converted to a single reporting currency using live rates from the
  [Frankfurter API](https://www.frankfurter.dev/) (free, no API key), with a cached
  and static-fallback path so a flaky connection never breaks a live demo
- **Multi-language UI**: English, Shona, and Ndebele
- **Validation**: flags missing tax invoices, missing customs bill-of-entry
  references, and transactions falling in the Dec 2025/Jan 2026 rate-transition
  window, before they're allowed to affect a claim
- **Branded Streamlit dashboard**: custom theme, KPI cards, charts, and a stylised
  "TTZ" logo — not the default Streamlit look

## Project structure

```
taxtrack-zim/
├── engine/              # Calculation engine (no third-party deps)
│   ├── models.py        # Transaction, VATReturn dataclasses
│   ├── rules.py         # Versioned, cited ZIMRA rate/category constants
│   ├── calculator.py    # Core VAT computation + audit trail builder
│   ├── validators.py    # Input data-quality checks
│   ├── ingestion.py     # CSV -> Transaction parsing
│   └── rates_fallback.json
├── data/
│   ├── sample_transactions.csv   # Simulated dataset, all transaction types
│   └── sample_generator.py       # Regenerates the sample dataset
├── services/
│   ├── fx.py             # Frankfurter API client, caching, fallback
│   └── i18n.py           # JSON-based translation loader
├── locales/               # en.json, sn.json, nd.json
├── ui/
│   ├── app.py              # Streamlit entrypoint (upload/sample data, settings)
│   ├── pages/               # Review / Return Summary / Calculation Trail
│   ├── components/branding.py   # Header, KPI cards, badges
│   └── assets/ttz_logo.svg
├── tests/
│   └── test_calculator.py   # 17 tests across all 5 transaction types + edge cases
├── ASSUMPTIONS.md         # Legal & computational assumptions register (for the report)
├── requirements.txt
└── .streamlit/config.toml   # Theme
```

## Running locally

Requires Python 3.10+.

```bash
git clone <your-repo-url>
cd taxtrack-zim
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run ui/app.py
```

Then, in the app: pick a language/currency/VAT category in the sidebar, and either
upload your own CSV (see the column format below) or click **"Use sample data"** to
explore with the bundled simulated dataset.

### Running the tests

```bash
python3 -m unittest discover -s tests -v
```

### Regenerating the sample dataset

```bash
python3 data/sample_generator.py
```

## CSV format for transactions

Required columns (see `data/sample_transactions.csv` for a full example):

| Column | Notes |
|---|---|
| `date` | `YYYY-MM-DD` (or `DD/MM/YYYY`) |
| `description` | Free text |
| `counterparty` | Free text |
| `transaction_type` | `sale`, `purchase`, `import`, or `adjustment` |
| `vat_treatment` | `standard`, `zero_rated`, `exempt`, `import`, or `adjustment` |
| `value_excl_vat` | Numeric |
| `currency` | `USD`, `ZWG`, `ZAR`, `EUR`, `GBP`, `BWP`, or `ZMW` |
| `has_valid_tax_invoice` | `TRUE`/`FALSE` — required to claim input tax on standard-rated purchases |
| `customs_bill_of_entry_ref` | Required to claim input tax on imports |
| `adjustment_target` | `output_tax` or `input_tax` (adjustment rows only) |
| `adjustment_reason` | e.g. `bad_debt_written_off`, `credit_note_issued` (adjustment rows only) |
| `vat_amount_override` | Signed VAT amount (adjustment rows; negative reduces the target) |

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (public, or private with Streamlit Cloud given access).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and
   click **"New app"**.
3. Select your repo/branch, and set **Main file path** to `ui/app.py`.
4. Under **Advanced settings → Secrets**, you don't need to add anything for the
   current build (Frankfurter needs no API key). If you later add a service that
   does need a key, paste it there in TOML format — never commit it to the repo.
   `.streamlit/secrets.toml.example` shows the expected format.
5. Click **Deploy**. First build takes a couple of minutes.
6. For the live demo: click **"Use sample data"** on first load rather than relying
   on a file upload, in case the venue's Wi-Fi is unreliable — the app also caches
   FX rates and falls back to a static table if Frankfurter is unreachable.

## Security notes

- No secrets are committed to this repository (`.streamlit/secrets.toml` is
  git-ignored; only the `.example` template is committed).
- Uploaded CSVs are parsed in-memory for the session only — never written to disk
  or persisted server-side.
- All bundled sample data is synthetic; no real names, TINs, or figures.

## Known limitations

See [`ASSUMPTIONS.md`](ASSUMPTIONS.md) for the full register. Headline items: the
First Schedule's exact current zero-rated/exempt split is not verified line-by-line;
the VAT registration threshold is configurable rather than fixed (sources conflict);
Shona/Ndebele translations are machine-assisted and would need native-speaker review
for production use; there's no integration with ZIMRA's e-filing system.
