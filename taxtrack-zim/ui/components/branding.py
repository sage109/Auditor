"""
Shared branded UI components: header with logo, and KPI tile cards for the
return summary. Kept as small reusable functions so every page looks
consistent and none of the styling is duplicated across pages/*.py.
"""
from __future__ import annotations
from pathlib import Path
import streamlit as st

from services.i18n import t

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "ttz_logo.svg"

CARD_CSS = """
<style>
.ttz-kpi-card {
    background: linear-gradient(135deg, #0E8A63 0%, #0B6E4F 100%);
    color: white;
    border-radius: 16px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.6rem;
    box-shadow: 0 4px 14px rgba(11, 110, 79, 0.18);
}
.ttz-kpi-card.negative {
    background: linear-gradient(135deg, #C9412E 0%, #A32E1F 100%);
    box-shadow: 0 4px 14px rgba(163, 46, 31, 0.18);
}
.ttz-kpi-card.neutral {
    background: linear-gradient(135deg, #2E5C8A 0%, #1F3D5C 100%);
    box-shadow: 0 4px 14px rgba(31, 61, 92, 0.18);
}
.ttz-kpi-label {
    font-size: 0.85rem;
    opacity: 0.85;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.2rem;
}
.ttz-kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
}
.ttz-header {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    margin-bottom: 0.4rem;
}
.ttz-header-title {
    font-size: 1.6rem;
    font-weight: 800;
    color: #0B3D2E;
    margin: 0;
}
.ttz-header-tagline {
    font-size: 0.95rem;
    color: #4A6459;
    margin: 0;
}
.ttz-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    margin-left: 0.4rem;
}
.ttz-badge.confirmed {
    background: #DCF3E6;
    color: #0B6E4F;
}
.ttz-badge.assumption {
    background: #FCEFC7;
    color: #8A6300;
}
</style>
"""


def inject_css():
    st.markdown(CARD_CSS, unsafe_allow_html=True)


def render_header(lang: str):
    inject_css()
    logo_svg = LOGO_PATH.read_text(encoding="utf-8")
    col1, col2 = st.columns([1, 6])
    with col1:
        st.markdown(
            f'<div style="max-width:70px">{logo_svg}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="ttz-header">'
            f'<div><p class="ttz-header-title">{t("app_title", lang)}</p>'
            f'<p class="ttz-header-tagline">{t("app_tagline", lang)}</p></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.divider()


def kpi_card(label: str, value: str, tone: str = "neutral"):
    css_class = {"positive": "", "negative": "negative", "neutral": "neutral"}.get(tone, "")
    st.markdown(
        f'<div class="ttz-kpi-card {css_class}">'
        f'<div class="ttz-kpi-label">{label}</div>'
        f'<div class="ttz-kpi-value">{value}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def rule_badge(status: str, lang: str) -> str:
    if status == "CONFIRMED":
        return f'<span class="ttz-badge confirmed">{t("confirmed_rule", lang)}</span>'
    return f'<span class="ttz-badge assumption">{t("assumption_flag", lang)}</span>'
