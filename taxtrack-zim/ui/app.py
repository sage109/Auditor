"""
TaxTrack Zim — Streamlit entrypoint.

Run from the repo root with:
    streamlit run ui/app.py

This page handles: language/currency/category selection, loading either the
bundled sample dataset or an uploaded CSV, and running the calculation once
so every other page (in ui/pages/) can just read `st.session_state`.
"""
from __future__ import annotations
import sys
from pathlib import Path

import streamlit as st

# Make the repo root importable regardless of where Streamlit is launched from.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.ingestion import parse_transactions_csv
from engine.calculator import calculate_return, StaticFXRateProvider
from engine.rules import VAT_CATEGORIES
from services.i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, t
from services.fx import FrankfurterFXProvider
from ui.components.branding import render_header

st.set_page_config(
    page_title="TaxTrack Zim",
    page_icon="🇿🇼",
    layout="wide",
)

SAMPLE_DATA_PATH = REPO_ROOT / "data" / "sample_transactions.csv"

if "lang" not in st.session_state:
    st.session_state.lang = DEFAULT_LANGUAGE
if "reporting_currency" not in st.session_state:
    st.session_state.reporting_currency = "USD"
if "vat_category" not in st.session_state:
    st.session_state.vat_category = "C"
if "period_label" not in st.session_state:
    st.session_state.period_label = "Current period"
if "transactions" not in st.session_state:
    st.session_state.transactions = None
if "vat_return" not in st.session_state:
    st.session_state.vat_return = None
if "row_errors" not in st.session_state:
    st.session_state.row_errors = []


# --- Sidebar: language, currency, category, period ---
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    lang_labels = {code: name for code, name in SUPPORTED_LANGUAGES.items()}
    lang_choice = st.selectbox(
        t("language", st.session_state.lang),
        options=list(lang_labels.keys()),
        format_func=lambda c: lang_labels[c],
        index=list(lang_labels.keys()).index(st.session_state.lang),
    )
    st.session_state.lang = lang_choice
    lang = st.session_state.lang

    st.session_state.reporting_currency = st.selectbox(
        t("reporting_currency", lang),
        options=["USD", "ZWG", "ZAR", "EUR", "GBP"],
        index=["USD", "ZWG", "ZAR", "EUR", "GBP"].index(st.session_state.reporting_currency),
    )
    st.session_state.vat_category = st.selectbox(
        t("vat_category", lang),
        options=list(VAT_CATEGORIES.keys()),
        index=list(VAT_CATEGORIES.keys()).index(st.session_state.vat_category),
        help=" / ".join(f"{k}: {v['description']}" for k, v in VAT_CATEGORIES.items()),
    )
    st.session_state.period_label = st.text_input(
        t("period_label", lang), value=st.session_state.period_label
    )

render_header(st.session_state.lang)
lang = st.session_state.lang

st.markdown(f"#### {t('upload_heading', lang)}")
st.caption(t("upload_help", lang))

col_a, col_b = st.columns([2, 1])
with col_a:
    uploaded = st.file_uploader("CSV", type=["csv"], label_visibility="collapsed")
with col_b:
    use_sample = st.button(f"📊 {t('use_sample_data', lang)}", use_container_width=True)

csv_source = None
if uploaded is not None:
    csv_source = uploaded.getvalue().decode("utf-8")
elif use_sample:
    csv_source = SAMPLE_DATA_PATH.read_text(encoding="utf-8")

if csv_source is not None:
    try:
        transactions, errors = parse_transactions_csv(csv_source)
        st.session_state.transactions = transactions
        st.session_state.row_errors = errors

        try:
            fx_provider = FrankfurterFXProvider()
        except Exception:
            fx_provider = StaticFXRateProvider(rates={"USD": 1})

        result = calculate_return(
            transactions=transactions,
            category=st.session_state.vat_category,
            period_label=st.session_state.period_label,
            reporting_currency=st.session_state.reporting_currency,
            fx_provider=fx_provider,
        )
        st.session_state.vat_return = result

        st.success(f"Loaded {len(transactions)} transactions.")
        if errors:
            st.warning(f"{len(errors)} row(s) could not be parsed — see below.")
            for e in errors:
                st.text(str(e))
    except Exception as e:
        st.error(f"Could not process the file: {e}")

if st.session_state.vat_return is not None:
    st.info(
        "Data loaded. Use the pages in the sidebar navigation "
        f"({t('nav_review', lang)}, {t('nav_summary', lang)}, {t('nav_trail', lang)}) "
        "to review the results."
    )
else:
    st.caption("No data loaded yet — upload a CSV or use the sample dataset above.")
