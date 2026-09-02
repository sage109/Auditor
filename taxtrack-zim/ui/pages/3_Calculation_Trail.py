"""Calculation Trail page — the auditable, line-by-line trail back to source transactions."""
from __future__ import annotations
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.i18n import t
from ui.components.branding import render_header

st.set_page_config(page_title="TaxTrack Zim — Calculation Trail", page_icon="🇿🇼", layout="wide")

lang = st.session_state.get("lang", "en")
render_header(lang)

vat_return = st.session_state.get("vat_return")
if vat_return is None:
    st.warning("No return calculated yet. Go to the home page to upload a CSV or load the sample dataset.")
    st.stop()

st.markdown(f"### {t('calculation_trail_heading', lang)}")
st.caption(t("calculation_trail_help", lang))

label_filter = st.multiselect(
    "Filter by line type",
    options=sorted(set(a.contribution_label for a in vat_return.audit_trail)),
    default=sorted(set(a.contribution_label for a in vat_return.audit_trail)),
)

for entry in vat_return.audit_trail:
    if entry.contribution_label not in label_filter:
        continue
    fallback_flag = " 🟡 fallback rate" if entry.rate_as_of is None and entry.exchange_rate_used != 1 else ""
    with st.expander(
        f"{entry.description} — {entry.contribution_label}: "
        f"{vat_return.reporting_currency} {entry.converted_amount:,.2f}{fallback_flag}"
    ):
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Transaction ID:**", entry.transaction_id)
            st.write("**Original amount:**", f"{entry.original_currency} {entry.original_amount:,.2f}")
            st.write("**Exchange rate used:**", f"{entry.exchange_rate_used}")
            st.write("**Rate as of:**", entry.rate_as_of or "fallback (offline rate table)")
        with c2:
            st.write("**Converted amount:**", f"{vat_return.reporting_currency} {entry.converted_amount:,.2f}")
            st.write("**Rule applied:**", entry.rule_applied)
        if entry.notes:
            st.markdown("**Notes / flags:**")
            for note in entry.notes:
                st.markdown(f"- {note}")

st.markdown("---")
st.markdown("#### Exchange rates used in this return")
st.json(vat_return.exchange_rates_used)
