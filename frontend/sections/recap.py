"""
Monthly recap: the month you review together, short — the total and how it
compares, what drove it, the targets, then settling up with one tap. The
sentences come from the pure recap_shaping.py; settling up is settle.settle_box.
"""
from __future__ import annotations

import datetime
from urllib.parse import urlencode

import streamlit as st

import analytics_shaping as shape
import recap_shaping
import ui
from common import SAO_PAULO, get_data
from sections.settle import settle_box


def _lines(title: str, lines: list[tuple[str, str | None]], empty: str) -> None:
    st.markdown(f"**{title}**")
    if lines:
        ui.kpi_lines(lines)
    else:
        st.caption(empty)


def render(token: str) -> None:
    today = datetime.datetime.now(SAO_PAULO).date()
    current = today.strftime("%Y-%m")
    # Reviewed together once a month ends: last month first, this month if you want to look early.
    options = shape.month_options(current, 12)
    month = st.selectbox("Month to review", options, index=1, format_func=shape.month_label, key="recap_month")

    data = get_data(f"analytics/shared?{urlencode({'month': month, 'months': 13})}", token, default=None)
    if not isinstance(data, dict):
        return
    df = shape.to_frame(data)
    targets = {t["primary_category"]: float(t["amount"])
               for t in get_data("category_targets/", token, default=[]) or [] if isinstance(t, dict)}
    summary = recap_shaping.month_recap(df, data["months"], month, data["is_partial"], data.get("first_date"), targets)

    if df[df["month"] == month].empty:
        st.info(f"Nothing shared in {shape.month_label(month)} yet.")
        with ui.card("recap_settle"):
            st.subheader("Settling up")
            settle_box(token, month, "recap")
        return

    with ui.card("recap_total"):
        ui.kpi(f"{summary['label']}: shared spending", summary["total"], summary["lines"], hero=True,
               help="Everything shared in the month, at full price.")
    left, right = st.columns(2, gap="small")
    with left, ui.card("recap_drivers", min_height=220):
        st.subheader("What drove it?")
        _lines("Day-to-day or fixed", summary["causes"], "Shown once there's a whole month to compare with.")
        _lines("Biggest moves", summary["moves"], "Shown once there's a whole month to compare with.")
    with right, ui.card("recap_targets", min_height=220):
        st.subheader("Are we on target?")
        _lines("Targets", summary["targets"], "No targets yet: set them in Settings → Monthly targets.")
    with ui.card("recap_settle"):
        st.subheader("Settling up")
        settle_box(token, month, "recap")
