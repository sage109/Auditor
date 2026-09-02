"""Review Transactions page — table view + validation issue list."""
from __future__ import annotations
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.i18n import t
from ui.components.branding import render_header

st.set_page_config(page_title="TaxTrack Zim — Review", page_icon="🇿🇼", layout="wide")

lang = st.session_state.get("lang", "en")
render_header(lang)

st.markdown(f"### {t('nav_review', lang)}")

transactions = st.session_state.get("transactions")
vat_return = st.session_state.get("vat_return")

if not transactions:
    st.warning("No transactions loaded yet. Go to the home page to upload a CSV or load the sample dataset.")
    st.stop()

import pandas as pd

rows = []
for txn in transactions:
    rows.append({
        "Date": txn.date,
        "Description": txn.description,
        "Counterparty": txn.counterparty,
        "Type": txn.transaction_type.value,
        "VAT treatment": txn.vat_treatment.value,
        "Value (excl. VAT)": float(txn.value_excl_vat),
        "Currency": txn.currency,
        "Tax invoice?": txn.has_valid_tax_invoice,
        "Bill of entry": txn.customs_bill_of_entry_ref or "",
        "Adjustment target": txn.adjustment_target.value if txn.adjustment_target else "",
        "Adjustment reason": txn.adjustment_reason.value if txn.adjustment_reason else "",
    })
df = pd.DataFrame(rows)

treatment_filter = st.multiselect(
    "Filter by VAT treatment",
    options=sorted(df["VAT treatment"].unique()),
    default=sorted(df["VAT treatment"].unique()),
)
filtered = df[df["VAT treatment"].isin(treatment_filter)]
st.dataframe(filtered, use_container_width=True, hide_index=True)

st.markdown(f"#### {t('validation_issues', lang)}")
if vat_return and vat_return.validation_issues:
    for issue in vat_return.validation_issues:
        icon = "🛑" if issue.severity.value == "error" else "⚠️"
        st.markdown(f"{icon} **{issue.code}** — {issue.message}")
else:
    st.success(t("no_issues", lang))
