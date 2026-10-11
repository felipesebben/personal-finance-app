"""
The shared look of every page: page setup, the header with its one-line
purpose, the "what this is for" box, and the callout that leads with an answer.

Colours and fonts come from .streamlit/config.toml; the few values repeated
here (for HTML blocks the theme can't reach) must stay in sync with it.
Every colour has one job: brand green for the household and actions, slate
for money owed, orange ▲ for spending more, blue ▼ for spending less.
"""
from html import escape
from pathlib import Path

import streamlit as st

APP_NAME = "Home Finances"
ASSETS = Path(__file__).resolve().parent / "assets"

BRAND = "#1f6f5c"
BRAND_SOFT = "#dcece6"
INK = "#17201c"
INK_2 = "#4d5a53"
LINE = "#d9ddd6"
OWED_SOFT = "#e6ebf2"
MORE = "#b5470f"   # spent more (orange)
LESS = "#1f5fa8"   # spent less (blue)

# Only what the theme can't do. Streamlit's internal class names change
# between versions, so nothing here targets them: just our own classes and
# tabular figures, which make every digit the same width so amounts line up.
_CSS = f"""
<style>
.stApp {{ font-variant-numeric: tabular-nums; }}
.hf-purpose {{ color: {INK_2}; margin: -0.6rem 0 0.4rem; max-width: 68ch; font-size: 1rem; }}
.hf-lede {{ display: flex; gap: 0.6rem; align-items: flex-start; background: {BRAND_SOFT};
           border-radius: 0.5rem; padding: 0.65rem 0.8rem; margin: 0.25rem 0 0.5rem; color: {INK}; }}
.hf-lede .hf-i {{ flex: none; width: 1.35rem; height: 1.35rem; border-radius: 50%; background: {BRAND};
                 color: #fff; font-weight: 700; font-size: 0.8rem; display: grid; place-items: center; margin-top: 0.1rem; }}
.hf-lede b {{ display: block; }}
.hf-callout {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.75rem;
              background: {OWED_SOFT}; border-left: 4px solid {BRAND}; border-radius: 0.5rem; padding: 0.9rem 1rem; color: {INK}; }}
.hf-callout .hf-label {{ font-size: 1.15rem; font-weight: 700; }}
.hf-callout .hf-detail {{ color: {INK_2}; font-size: 0.85rem; }}
.hf-callout .hf-amount {{ font-size: 1.6rem; font-weight: 700; white-space: nowrap; }}
</style>
"""


def setup(page_title: str, layout: str = "wide") -> None:
    """Call first on every page: tab title, favicon, sidebar logo and the shared CSS."""
    st.set_page_config(page_title=f"{page_title} · {APP_NAME}", page_icon=str(ASSETS / "icon.svg"), layout=layout)
    st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icon.svg"))
    st.html(_CSS)


def page_header(title: str, purpose: str) -> None:
    """The page title and one plain sentence saying what the page is for."""
    st.title(title)
    st.html(f'<p class="hf-purpose">{escape(purpose)}</p>')


def lede(headline: str, body: str = "") -> None:
    """The green "what this is for" box that opens a section or tab: two lines at most."""
    text = f"<b>{escape(headline)}</b>{escape(body)}" if body else f"<b>{escape(headline)}</b>"
    st.html(f'<div class="hf-lede"><span class="hf-i" aria-hidden="true">i</span><div>{text}</div></div>')


def callout(label: str, amount: str = "", detail: str = "") -> None:
    """Leads with the answer ("Ana owes you", "R$ 247,90"), before the table that explains it."""
    detail_html = f'<div class="hf-detail">{escape(detail)}</div>' if detail else ""
    amount_html = f'<div class="hf-amount">{escape(amount)}</div>' if amount else ""
    st.html(
        f'<div class="hf-callout"><div><div class="hf-label">{escape(label)}</div>{detail_html}</div>'
        f"{amount_html}</div>"
    )
