"""
Altair charts for the Analytics Overview, built from analytics_shaping frames.

No Streamlit import: each function returns a chart the page hands to
st.altair_chart. One accent colour marks what's selected; everything else
is neutral grey, so the eye goes where the question is.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

from analytics_shaping import BRL_AXIS_EXPR, month_label, pct_text, short_brl, signed_brl
from money import format_brl

# Home Finances palette (see frontend/.streamlit/config.toml): brand green marks
# what is selected; blue and orange are reserved for "less" / "more", so they
# never encode plain magnitude here.
ACCENT = "#1f6f5c"
GREY = "#c3c9c3"
MUTED = "#6f7a74"  # readable on the light theme background
HEAT_RANGE = ["#eef5f2", "#1f6f5c"]  # light to brand green, for magnitude


def trend_chart(totals: pd.Series, selected: str, is_partial: bool, average: float | None) -> alt.LayerChart:
    """
    Columns per month, the selected month in the accent colour. A month in
    progress is drawn faded with a dashed outline and labelled "to date" —
    no projection. A dashed rule marks the average of the last 3 full months.
    """
    data = pd.DataFrame({"month": totals.index, "amount": totals.values})
    data["partial"] = is_partial & (data["month"] == selected)
    data["selected"] = data["month"] == selected
    data["label"] = [
        month_label(m, short=True) + (" (to date)" if p else "") for m, p in zip(data["month"], data["partial"])
    ]
    data["value_label"] = data["amount"].map(short_brl)
    data["amount_brl"] = data["amount"].map(format_brl)
    order = list(data["label"])

    x = alt.X("label:N", sort=order, title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True))
    y = alt.Y("amount:Q", title=None, axis=alt.Axis(labelExpr=BRL_AXIS_EXPR, tickCount=4))
    tooltip = [alt.Tooltip("label:N", title="Month"), alt.Tooltip("amount_brl:N", title="Total")]

    base = alt.Chart(data)
    bars = base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=x, y=y, tooltip=tooltip,
        color=alt.condition(alt.datum.selected, alt.value(ACCENT), alt.value(GREY)),
        opacity=alt.condition(alt.datum.partial, alt.value(0.45), alt.value(1.0)),
    )
    outline = base.transform_filter(alt.datum.partial).mark_bar(
        filled=False, stroke=ACCENT, strokeDash=[4, 3], strokeWidth=1.5,
    ).encode(x=x, y=y)
    labels = base.mark_text(dy=-7, fontSize=11).encode(x=x, y=y, text="value_label:N")
    layers = [bars, outline, labels]

    if average is not None:
        avg = pd.DataFrame({"amount": [average], "text": [f"3-month avg {short_brl(average)}"]})
        rule = alt.Chart(avg).mark_rule(strokeDash=[6, 4], color=MUTED).encode(y="amount:Q")
        note = alt.Chart(avg).mark_text(align="left", baseline="bottom", dx=2, dy=-2, color=MUTED, fontSize=11).encode(
            y="amount:Q", text="text:N", x=alt.value(0),
        )
        layers += [rule, note]

    return alt.layer(*layers).properties(height=280)


def comparison_bars(comparison: pd.DataFrame, by: str, previous_title: str) -> alt.LayerChart:
    """
    Horizontal bars for the selected month, largest first, with a tick at
    the previous period and a label carrying the R$ and % change.
    """
    data = comparison.copy()
    data["current_brl"] = data["current"].map(format_brl)
    data["previous_brl"] = data["previous"].map(format_brl)
    data["text"] = [
        f"{short_brl(c)}  {signed_brl(ch)} ({pct_text(p)})"
        for c, ch, p in zip(data["current"], data["change"], data["pct"])
    ]
    data["label_x"] = data[["current", "previous"]].max(axis=1)
    order = list(data[by])
    top = float(data["label_x"].max()) if not data.empty else 0.0

    y = alt.Y(f"{by}:N", sort=order, title=None, axis=alt.Axis(labelLimit=160))
    scale = alt.Scale(domain=[0, max(top * 1.6, 1.0)])
    tooltip = [
        alt.Tooltip(f"{by}:N", title="Category"),
        alt.Tooltip("current_brl:N", title="This month"),
        alt.Tooltip("previous_brl:N", title=previous_title),
    ]

    base = alt.Chart(data)
    bars = base.mark_bar(color=ACCENT, cornerRadiusTopRight=3, cornerRadiusBottomRight=3).encode(
        y=y, tooltip=tooltip,
        x=alt.X("current:Q", title=None, scale=scale, axis=alt.Axis(labelExpr=BRL_AXIS_EXPR, tickCount=4)),
    )
    ticks = base.mark_tick(color=MUTED, thickness=2.5, size=22).encode(y=y, x="previous:Q", tooltip=tooltip)
    text = base.mark_text(align="left", dx=6, fontSize=11).encode(y=y, x="label_x:Q", text="text:N")
    return alt.layer(bars, ticks, text).properties(height=max(36 * len(data), 80))


def heatmap_chart(long: pd.DataFrame, months: list[str]) -> alt.LayerChart:
    """Categories × months, one sequential hue; each cell shows a short BRL amount."""
    data = long.copy()
    data["month_label"] = data["month"].map(lambda m: month_label(m, short=True))
    data["text"] = [short_brl(a) if a else "–" for a in data["amount"]]
    data["amount_brl"] = data["amount"].map(format_brl)
    peak = float(data["amount"].max()) if not data.empty else 0.0
    data["dark"] = data["amount"] > peak * 0.55
    categories = list(dict.fromkeys(data["primary_category"]))
    x = alt.X("month_label:N", sort=[month_label(m, short=True) for m in months], title=None,
              axis=alt.Axis(labelAngle=0, orient="top", labelOverlap=True))
    y = alt.Y("primary_category:N", sort=categories, title=None, axis=alt.Axis(labelLimit=160))

    base = alt.Chart(data)
    cells = base.mark_rect(cornerRadius=2, stroke="white", strokeWidth=1).encode(
        x=x, y=y,
        color=alt.Color("amount:Q", scale=alt.Scale(range=HEAT_RANGE, domainMin=0), legend=None),
        tooltip=[
            alt.Tooltip("primary_category:N", title="Category"),
            alt.Tooltip("month_label:N", title="Month"),
            alt.Tooltip("amount_brl:N", title="Total"),
        ],
    )
    text = base.mark_text(fontSize=10).encode(
        x=x, y=y, text="text:N",
        color=alt.condition(alt.datum.dark, alt.value("white"), alt.value("#17201c")),
    )
    return alt.layer(cells, text).properties(height=max(30 * len(categories), 80))


def cost_type_chart(split: pd.DataFrame, current_title: str, previous_title: str) -> alt.Chart:
    """One 100% bar per period, Fixed in the accent colour."""
    rows = []
    for _, r in split.iterrows():
        rows.append({"period": current_title, "cost_type": r["cost_type"], "amount": r["current"], "share": r["current_share"]})
        rows.append({"period": previous_title, "cost_type": r["cost_type"], "amount": r["previous"], "share": r["previous_share"]})
    data = pd.DataFrame(rows, columns=["period", "cost_type", "amount", "share"])
    data["amount_brl"] = data["amount"].map(format_brl)
    types = sorted(data["cost_type"].unique(), key=lambda t: (t != "Fixed", t != "Variable", t))
    palette = [ACCENT if t == "Fixed" else GREY if t == "Variable" else "#e3e7e2" for t in types]
    return alt.Chart(data).mark_bar().encode(
        y=alt.Y("period:N", sort=[current_title, previous_title], title=None),
        x=alt.X("amount:Q", stack="normalize", title=None, axis=alt.Axis(format="%", tickCount=4)),
        color=alt.Color("cost_type:N", sort=types, scale=alt.Scale(domain=types, range=palette),
                        legend=alt.Legend(title=None, orient="bottom")),
        order=alt.Order("cost_type_order:Q"),
        tooltip=[
            alt.Tooltip("period:N", title="Period"),
            alt.Tooltip("cost_type:N", title="Cost type"),
            alt.Tooltip("amount_brl:N", title="Total"),
            alt.Tooltip("share:Q", title="Share", format=".0%"),
        ],
    ).transform_calculate(
        cost_type_order=f"indexof({types!r}, datum.cost_type)",
    ).properties(height=110)


def joint_pace_chart(data: pd.DataFrame, this_month: str, usual: str, days_in_month: int) -> alt.Chart:
    """
    Cumulative spending through the month: this month as a solid accent line
    (it stops at today), the usual month as a dashed grey line across all days.
    """
    return alt.Chart(data).mark_line(point=False, strokeWidth=2.5).encode(
        x=alt.X("day:Q", title="Day of the month", scale=alt.Scale(domain=[1, days_in_month]),
                axis=alt.Axis(tickMinStep=1, format="d")),
        y=alt.Y("amount:Q", title=None, axis=alt.Axis(labelExpr=BRL_AXIS_EXPR, tickCount=4)),
        color=alt.Color("series:N", scale=alt.Scale(domain=[this_month, usual], range=[ACCENT, MUTED]),
                        legend=alt.Legend(title=None, orient="bottom")),
        strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(domain=[this_month, usual], range=[[1, 0], [6, 4]]),
                                  legend=None),
        tooltip=[
            alt.Tooltip("series:N", title=" "),
            alt.Tooltip("day:Q", title="Day"),
            alt.Tooltip("amount_brl:N", title="Spent by then"),
        ],
    ).properties(height=260)
