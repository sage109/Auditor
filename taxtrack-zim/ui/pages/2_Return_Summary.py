"""Return Summary page — the headline VAT7-style summary with KPI cards and charts."""
from __future__ import annotations
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.i18n import t
from ui.components.branding import render_header, kpi_card

st.set_page_config(page_title="TaxTrack Zim — Return Summary", page_icon="🇿🇼", layout="wide")

lang = st.session_state.get("lang", "en")
render_header(lang)

vat_return = st.session_state.get("vat_return")
if vat_return is None:
    st.warning("No return calculated yet. Go to the home page to upload a CSV or load the sample dataset.")
    st.stop()

totals = vat_return.totals
currency = vat_return.reporting_currency

st.markdown(f"### {t('nav_summary', lang)} — {vat_return.period_label} (Category {vat_return.category})")

col1, col2, col3 = st.columns(3)
with col1:
    kpi_card(t("output_tax", lang), f"{currency} {totals.output_tax:,.2f}", tone="neutral")
with col2:
    kpi_card(t("input_tax", lang), f"{currency} {totals.input_tax:,.2f}", tone="neutral")
with col3:
    net = totals.net_payable_or_refundable
    if net >= 0:
        kpi_card(t("net_payable", lang), f"{currency} {net:,.2f}", tone="negative")
    else:
        kpi_card(t("net_refundable", lang), f"{currency} {abs(net):,.2f}", tone="positive")

st.markdown("&nbsp;", unsafe_allow_html=True)

col4, col5, col6 = st.columns(3)
with col4:
    kpi_card(t("standard_supplies", lang), f"{currency} {totals.total_value_of_standard_supplies:,.2f}", tone="neutral")
with col5:
    kpi_card(t("zero_rated_supplies", lang), f"{currency} {totals.total_value_of_zero_rated_supplies:,.2f}", tone="neutral")
with col6:
    kpi_card(t("exempt_supplies", lang), f"{currency} {totals.total_value_of_exempt_supplies:,.2f}", tone="neutral")

st.markdown("---")

# --- Chart: output vs input tax, plus adjustments ---
try:
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Output tax", "Output adjustments", "Input tax", "Input adjustments"],
        y=[
            float(totals.output_tax),
            float(totals.output_tax_adjustments),
            float(totals.input_tax),
            float(totals.input_tax_adjustments),
        ],
        marker_color=["#0E8A63", "#F2B705", "#2E5C8A", "#C9412E"],
    ))
    fig.update_layout(
        title="Return components",
        yaxis_title=f"Amount ({currency})",
        showlegend=False,
        height=380,
        margin=dict(t=50, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
except ImportError:
    st.info("Install `plotly` to see the return-components chart (see requirements.txt).")

st.markdown(f"#### {t('validation_issues', lang)}")
if vat_return.validation_issues:
    errors = [i for i in vat_return.validation_issues if i.severity.value == "error"]
    warnings = [i for i in vat_return.validation_issues if i.severity.value == "warning"]
    st.metric("Errors (blocking a claim)", len(errors))
    st.metric("Warnings (assumptions applied)", len(warnings))
else:
    st.success(t("no_issues", lang))

# --- Download ---
import io
import csv as csv_module

buf = io.StringIO()
writer = csv_module.writer(buf)
writer.writerow(["Line", "Amount", "Currency"])
writer.writerow(["Standard-rated supplies", totals.total_value_of_standard_supplies, currency])
writer.writerow(["Zero-rated supplies", totals.total_value_of_zero_rated_supplies, currency])
writer.writerow(["Exempt supplies", totals.total_value_of_exempt_supplies, currency])
writer.writerow(["Output tax", totals.output_tax, currency])
writer.writerow(["Output tax adjustments", totals.output_tax_adjustments, currency])
writer.writerow(["Input tax", totals.input_tax, currency])
writer.writerow(["Input tax adjustments", totals.input_tax_adjustments, currency])
writer.writerow(["Net payable (+) / refundable (-)", totals.net_payable_or_refundable, currency])

st.download_button(
    label=f"⬇️ {t('download_return', lang)}",
    data=buf.getvalue(),
    file_name=f"taxtrack_zim_return_{vat_return.category}_{vat_return.period_label}.csv",
    mime="text/csv",
)
