"""
Altair charts for the "This month" (daily) view, built from daily_shaping
frames. No Streamlit import: each function returns a chart for
st.altair_chart.

The same palette and rules as analytics_charts: brand green for the month
in question, grey for what it's compared with (told apart by a dash, not
by a second hue), one green ramp for magnitude, and never red/green for
good/bad.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

from analytics_charts import ACCENT, BAR_ROW, names_width, GREY, MUTED, X_AXIS, finish, name_axis, x_title, y_title
from analytics_shaping import BRL_AXIS_EXPR, short_brl

from daily_shaping import WEEKDAYS

INK = "#17201c"
LAST_MONTH = "#7d8780"   # a mid grey: last month, solid
USUAL_LINE = "#a9b1ab"   # lighter, and dashed: the usual month sits behind both
EMPTY_DAY = "#f1f3f0"    # a day with nothing spent
FUTURE_DAY = "#ffffff"
HEAT = ["#d7ebe2", ACCENT]  # light to brand green; the lightest step still reads as "something"
HEIGHT = 400  # the running-total chart, axes and legend included (as Streamlit sizes it)
SPARK_HEIGHT = 68  # every card's chart slot, so a row of cards lines up
TRACK = "#e9ece8"  # the empty part of a progress bar
MORE, LESS = "#b5470f", "#1f5fa8"  # spent more (orange) / less (blue), as ui.MORE / ui.LESS


# Each comparison's line: this month brand green; the others greys told
# apart by their dash (the legend names them); the target in ink, dotted.
ROLE_STYLE = {
    "this": (ACCENT, [1, 0], 3),
    "last": (LAST_MONTH, [1, 0], 2),
    "usual": (USUAL_LINE, [6, 4], 2),
    "year": (USUAL_LINE, [2, 3], 2),
    "last_year": ("#8f9892", [9, 3, 2, 3], 2),
    "target": (INK, [1, 3], 1.5),
}


def running_total_chart(frame: pd.DataFrame, order: list[str], days: int,
                        today: int | None, key: str, roles: list[str] | None = None) -> alt.LayerChart:
    """
    Cumulative spending through the month: this month (brand green, ends
    today, labelled) against each comparison in `order`, styled by its role
    (ROLE_STYLE; by default this month, last month, usual month).
    Hovering anywhere shows them all at that day.
    """
    roles = roles or ["this", "last", "usual"][:len(order)]
    present = [x for x in order if x in set(frame["series"])]
    by_name = dict(zip(order, roles))
    colours = {x: ROLE_STYLE[by_name[x]][0] for x in present}
    dashes = {x: ROLE_STYLE[by_name[x]][1] for x in present}
    widths = {x: ROLE_STYLE[by_name[x]][2] for x in present}

    x = alt.X("day:Q", scale=alt.Scale(domain=[1, days], nice=False),
              axis=alt.Axis(values=[1, 5, 10, 15, 20, 25, days], format="d", grid=False,
                            **x_title("Day of the month")))
    y = alt.Y("amount:Q", axis=alt.Axis(labelExpr=BRL_AXIS_EXPR, tickCount=5, domain=False, ticks=False,
                                        **y_title("Spent so far")))
    # One legend: colour and dash share the field and settings, so Vega-Lite merges them
    # and the usual month shows dashed there too.
    # Offset clear of the y title, which sits at the top of its axis.
    legend = alt.Legend(title=None, orient="top", direction="horizontal", symbolType="stroke",
                        symbolStrokeWidth=3, symbolSize=300, offset=26)
    colour = alt.Color("series:N", sort=present,
                       scale=alt.Scale(domain=present, range=[colours[s] for s in present]), legend=legend)
    dash = alt.StrokeDash("series:N", sort=present,
                          scale=alt.Scale(domain=present, range=[dashes[s] for s in present]), legend=legend)
    width = alt.StrokeWidth("series:N", sort=present,
                            scale=alt.Scale(domain=present, range=[widths[s] for s in present]), legend=None)

    base = alt.Chart(frame)
    hover = alt.selection_point(name=f"{key}_hover", nearest=True, on="pointerover", fields=["day"],
                                empty=False, clear="pointerout")
    # Straight segments: money arrives on days, it doesn't drift in between.
    lines = base.mark_line(interpolate="linear").encode(x=x, y=y, color=colour, strokeDash=dash, strokeWidth=width)
    # An invisible point per day catches the pointer anywhere near the lines.
    catcher = base.mark_point(opacity=0, size=600).encode(x=x).add_params(hover)
    dots = base.mark_point(filled=True, size=55, stroke="white", strokeWidth=1.5).encode(
        x=x, y=y, color=colour, opacity=alt.condition(hover, alt.value(1), alt.value(0)))
    tooltip = [alt.Tooltip("day:Q", title="Day")] + [alt.Tooltip(f"{s}:N", title=s) for s in present]
    rule = base.transform_pivot("series", value="amount_brl", groupby=["day"]).mark_rule(
        color=MUTED, strokeWidth=1).encode(x=x, opacity=alt.condition(hover, alt.value(0.5), alt.value(0)),
                                           tooltip=tooltip)
    layers = [lines, rule, catcher, dots]

    # Label where this month has got to.
    this = frame[frame["series"] == present[0]]
    if not this.empty:
        end = this.iloc[[-1]].assign(label=lambda d: d["amount"].map(short_brl))
        layers.append(alt.Chart(end).mark_text(align="left", dx=8, dy=-8, fontWeight="bold", color=INK).encode(
            x=x, y=y, text="label:N"))
    if today is not None:
        marker = pd.DataFrame({"day": [today], "text": ["today"]})
        layers.append(alt.Chart(marker).mark_rule(color=GREY, strokeWidth=1).encode(x=x))
        # At the foot of its line, just above the axis: the top is where the value label sits, and below the
        # plot it would push the chart's bounds down.
        layers.append(alt.Chart(marker).mark_text(align="left", baseline="bottom", dx=4, dy=-4,
                                                  color=MUTED, fontSize=11).encode(x=x, y=alt.datum(0),
                                                                                   text="text:N"))
    return finish(alt.layer(*layers), HEIGHT)


def calendar_chart(cal: pd.DataFrame, max_amount: float, title: str | None = None,
                   row_height: int = 42, compact: bool = False) -> alt.LayerChart:
    """
    A month as a calendar (weeks down, Monday first across), each day
    shaded by what was spent: lighter = less, brand green = `max_amount`
    or more (daily_shaping.calendar_scale_max: a typical big day, so one
    rent payment doesn't wash every other day out; the tooltip has the
    exact amount). Days with nothing are pale grey; days still to come are
    blank; today is outlined. Share `max_amount` between calendars so their
    shades compare. No legend inside: both calendars must be the same size
    side by side, so the page draws one shared legend under them (a legend
    on one only squeezed it). No click selection either: Streamlit 1.50
    can't return one from a layered chart, so the page offers a day picker.
    """
    top = max(max_amount, 1.0)
    x = alt.X("weekday_name:O", sort=WEEKDAYS, title=None,
              scale=alt.Scale(paddingInner=0.08),
              axis=alt.Axis(orient="top", labelAngle=0, ticks=False, domain=False, labelColor=MUTED,
                            labelPadding=4 if compact else 6, labelFontSize=9 if compact else 11,
                            # compact: the weekday's first letter, like a pocket calendar
                            labelExpr="substring(datum.label, 0, 1)" if compact else "datum.label"))
    y = alt.Y("week:O", title=None, axis=None, scale=alt.Scale(paddingInner=0.08))
    tooltip = [alt.Tooltip("label:N", title="Day"), alt.Tooltip("amount_brl:N", title="Spent"),
               alt.Tooltip("count:Q", title="Expenses"), alt.Tooltip("top_category:N", title="Biggest category")]
    base = alt.Chart(cal)
    cell = dict(cornerRadius=3 if compact else 5)

    background = base.mark_rect(**cell).encode(
        x=x, y=y,
        color=alt.condition("datum.state === 'future'", alt.value(FUTURE_DAY), alt.value(EMPTY_DAY)),
        stroke=alt.condition("datum.state === 'future'", alt.value("#e3e7e2"), alt.value("transparent")),
        tooltip=tooltip,
    )
    spend = base.transform_filter("datum.amount > 0").mark_rect(**cell).encode(
        x=x, y=y,
        color=alt.Color("amount:Q", scale=alt.Scale(domain=[0, top], range=HEAT, clamp=True), legend=None),
        tooltip=tooltip,
    )
    today = base.transform_filter("datum.state === 'today'").mark_rect(
        filled=False, stroke=INK, strokeWidth=2, **cell).encode(x=x, y=y)
    # White on the darker greens, faint on days still to come, ink otherwise.
    ink = (f"datum.amount > {top * 0.55} ? 'white' : "
           f"(datum.state === 'future' ? '#b4bbb5' : '{INK}')")
    numbers = base.transform_calculate(ink=ink).mark_text(fontSize=9 if compact else 12).encode(
        x=x, y=y, text="day:Q", fill=alt.Fill("ink:N", scale=None), tooltip=tooltip,
    )
    weeks = int(cal["week"].max()) + 1
    # As wide as its column (use_container_width); rows of `row_height`, plus the weekday header.
    chart = alt.layer(background, spend, today, numbers).properties(height=weeks * row_height + 24)
    if title:
        chart = chart.properties(title=alt.TitleParams(title, anchor="start", fontSize=14, color=INK))
    return finish(chart)


def weekday_chart(profile: pd.DataFrame) -> alt.LayerChart:
    """Average spent per weekday; the most expensive weekday in brand green, the rest grey."""
    top = profile["average"].max()
    data = profile.assign(is_top=profile["average"].eq(top) & (top > 0),
                          label=profile["average"].map(short_brl))
    x = alt.X("weekday_name:O", sort=WEEKDAYS, title=None, axis=alt.Axis(labelAngle=0, ticks=False))
    y = alt.Y("average:Q", axis=alt.Axis(labelExpr=BRL_AXIS_EXPR, tickCount=3, domain=False, ticks=False,
                                         **y_title("Average per day")))
    tooltip = [alt.Tooltip("weekday_name:N", title="Weekday"), alt.Tooltip("average_brl:N", title="Average spent"),
               alt.Tooltip("days:Q", title="Days counted")]
    bars = alt.Chart(data).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=24).encode(
        x=x, y=y, tooltip=tooltip,
        color=alt.condition(alt.datum.is_top, alt.value(ACCENT), alt.value(GREY)))
    labels = alt.Chart(data).mark_text(dy=-7, fontSize=11, color=INK).encode(x=x, y=y, text="label:N")
    return finish(alt.layer(bars, labels), 240)


# --- sparklines for the cards ---------------------------------------------------
# No axes, no legend: the card's text says what they are, a tooltip gives the
# numbers. Brand green marks the month in question, grey the others.

def _spark(chart, height: int = SPARK_HEIGHT):
    return chart.properties(height=height, padding={"left": 2, "right": 6, "top": 12, "bottom": 2}).configure(
        background="transparent").configure_view(strokeWidth=0)


def spark_running(frame: pd.DataFrame, order: list[str], days: int, height: int = 120) -> alt.LayerChart:
    """
    The hero card's sparkline: this month's running total (brand green, to
    today, with a dot) over last month's (grey), each named at its end.
    """
    present = [s for s in order[:2] if s in set(frame["series"])]
    data = frame[frame["series"].isin(present)]
    colours = [ACCENT, LAST_MONTH][:len(present)]
    x = alt.X("day:Q", axis=None, scale=alt.Scale(domain=[1, days], nice=False))
    y = alt.Y("amount:Q", axis=None, scale=alt.Scale(zero=True))
    colour = alt.Color("series:N", sort=present, scale=alt.Scale(domain=present, range=colours), legend=None)
    tooltip = [alt.Tooltip("series:N", title="Month"), alt.Tooltip("day:Q", title="Day"),
               alt.Tooltip("amount_brl:N", title="Spent by then")]
    lines = alt.Chart(data).mark_line(interpolate="linear").encode(
        x=x, y=y, color=colour, tooltip=tooltip,
        strokeWidth=alt.StrokeWidth("series:N", sort=present, legend=None,
                                    scale=alt.Scale(domain=present, range=[2.5, 1.5][:len(present)])))
    ends = data.groupby("series", as_index=False).last()
    ends = ends.assign(name=ends["series"].str.replace(" (so far)", "", regex=False).str[:3])
    end = alt.Chart(ends)
    dots = end.mark_point(filled=True, size=40, stroke="white", strokeWidth=1).encode(
        x=x, y=y, color=colour, tooltip=tooltip)
    labels = end.mark_text(align="left", dx=5, fontSize=10, color=MUTED).encode(x=x, y=y, text="name:N")
    baseline = alt.Chart(pd.DataFrame({"zero": [0.0]})).mark_rule(color="#aab2ac").encode(
        y=alt.Y("zero:Q", axis=None))  # axis=None like the other layers, or Vega-Lite fails to compile
    return _spark(alt.layer(baseline, lines, dots, labels), height)


def spark_bars(frame: pd.DataFrame, value: str, tooltip_title: str, reference: float | None = None) -> alt.LayerChart:
    """
    One bar per row of `frame` (label, `value`, `<value>_brl`,
    is_selected), the selected one in brand green; `reference` adds a
    dashed ink line (e.g. the usual month).
    """
    x = alt.X("label:N", sort=None, axis=alt.Axis(title=None, labelAngle=0, labelFontSize=9, labelColor=MUTED,
                                                  ticks=False, domain=True, domainColor="#aab2ac", labelPadding=3))
    y = alt.Y(f"{value}:Q", axis=None, scale=alt.Scale(zero=True))
    tooltip = [alt.Tooltip("label:N", title="Month"), alt.Tooltip(f"{value}_brl:N", title=tooltip_title)]
    bars = alt.Chart(frame).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=x, y=y, tooltip=tooltip,
        color=alt.condition("datum.is_selected", alt.value(ACCENT), alt.value(GREY)))
    layers = [bars]
    if reference is not None:
        layers.append(alt.Chart(pd.DataFrame({"ref": [reference]})).mark_rule(
            color=INK, strokeDash=[3, 2], strokeWidth=1).encode(y=alt.Y("ref:Q", axis=None)))
    return _spark(alt.layer(*layers))


def spark_days(cal: pd.DataFrame) -> alt.Chart:
    """Each day of a month as a thin bar (future days empty), for the "days with spending" card."""
    x = alt.X("day:O", axis=alt.Axis(title=None, labels=False, ticks=False, domainColor="#aab2ac"))
    y = alt.Y("amount:Q", axis=None, scale=alt.Scale(zero=True))
    tooltip = [alt.Tooltip("label:N", title="Day"), alt.Tooltip("amount_brl:N", title="Spent")]
    return _spark(alt.Chart(cal).mark_bar(color=ACCENT, cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=x, y=y, tooltip=tooltip))


def spark_progress(spent_share: float, time_share: float) -> alt.LayerChart:
    """
    A progress bar: how much of the reference month is spent (orange when
    ahead of the month, brand green otherwise), with an ink tick at how
    much of the month has gone.
    """
    ahead = spent_share > time_share
    shown = min(max(spent_share, 0.0), 1.0)
    data = pd.DataFrame({"start": [0.0], "end": [shown], "track": [1.0], "time": [time_share],
                         "spent_text": [f"{spent_share:.0%}"], "time_text": [f"{time_share:.0%}"]})
    scale = alt.Scale(domain=[0, 1])
    tooltip = [alt.Tooltip("spent_text:N", title="Spent"), alt.Tooltip("time_text:N", title="Month gone")]
    base = alt.Chart(data)
    track = base.mark_bar(color=TRACK, cornerRadius=4, height=12).encode(
        x=alt.X("start:Q", scale=scale, axis=None), x2="track:Q", tooltip=tooltip)
    fill = base.mark_bar(color=MORE if ahead else ACCENT, cornerRadius=4, height=12).encode(
        x=alt.X("start:Q", scale=scale, axis=None), x2="end:Q", tooltip=tooltip)
    tick = base.mark_tick(color=INK, thickness=2, size=22).encode(
        x=alt.X("time:Q", scale=scale, axis=None), tooltip=tooltip)
    # Say what the two marks are, under the bar: what's spent at its end, the month at the tick.
    spent_label = base.mark_text(align="left", baseline="bottom", dy=-10, fontSize=10, color=INK).encode(
        x=alt.X("start:Q", scale=scale, axis=None), text=alt.value(f"Spent {spent_share:.0%}"))
    time_label = base.mark_text(baseline="top", dy=14, fontSize=10, color=MUTED).encode(
        x=alt.X("time:Q", scale=scale, axis=None), text=alt.value(f"{time_share:.0%} of the month"))
    return _spark(alt.layer(track, fill, tick, spent_label, time_label))


def changes_chart(changes: pd.DataFrame) -> alt.LayerChart:
    """
    Where the difference comes from: one horizontal bar per category, the
    change against the comparison, orange to the right for more, blue to
    the left for less, labelled with an arrow and the amount (text in ink).
    """
    order = list(changes["name"])
    y = alt.Y("name:N", sort=order, axis=name_axis(names_width(order)))
    # Room past each end of the bars for their labels, so they never reach the category names.
    low, high = min(changes["change"].min(), 0.0), max(changes["change"].max(), 0.0)
    pad = 0.28 * (high - low or 1.0)
    domain = [low - pad if low < 0 else 0.0, high + pad if high > 0 else 0.0]
    x = alt.X("change:Q", scale=alt.Scale(domain=domain, nice=False),
              axis=alt.Axis(labelExpr=BRL_AXIS_EXPR, tickCount=4, **x_title("Change")))
    tooltip = [alt.Tooltip("name:N", title="Category"), alt.Tooltip("now_brl:N", title="This month"),
               alt.Tooltip("then_brl:N", title="Compared with"), alt.Tooltip("change_brl:N", title="Change")]
    data = changes.assign(label=[("▲ " if c > 0 else "▼ " if c < 0 else "") + short_brl(abs(c))
                                 for c in changes["change"]])
    base = alt.Chart(data)
    bars = base.mark_bar(cornerRadius=4, height=18).encode(
        x=x, y=y, tooltip=tooltip,
        color=alt.Color("direction:N", scale=alt.Scale(domain=["more", "less", "same"], range=[MORE, LESS, GREY]),
                        legend=None))
    more = base.transform_filter("datum.change >= 0").mark_text(
        align="left", dx=4, fontSize=11, color=INK).encode(x=x, y=y, text="label:N")
    less = base.transform_filter("datum.change < 0").mark_text(
        align="right", dx=-4, fontSize=11, color=INK).encode(x=x, y=y, text="label:N")
    zero = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=MUTED).encode(x="z:Q")
    return finish(alt.layer(bars, zero, more, less), BAR_ROW * max(len(order), 1) + X_AXIS)



def months_chart(frame: pd.DataFrame, references: list[tuple[str, float]]) -> alt.LayerChart:
    """
    "Where are we heading?": each month's total as a line (daily_shaping.
    months_frame), the selected month a brand-green dot (hollow while it's
    still going: shown so far, never projected), and each reference (the
    12-month average, the target) a quiet horizontal line named at its end.
    """
    order = list(frame["label"])
    x = alt.X("label:N", sort=order, axis=alt.Axis(labelAngle=0, ticks=False, **x_title("Month")))
    y = alt.Y("amount:Q", axis=alt.Axis(labelExpr=BRL_AXIS_EXPR, tickCount=4, domain=False, ticks=False,
                                        **y_title("Spent in the month")),
              scale=alt.Scale(zero=True))
    tooltip = [alt.Tooltip("label:N", title="Month"), alt.Tooltip("amount_brl:N", title="Spent")]
    data = frame.assign(text=frame["amount"].map(short_brl))
    base = alt.Chart(data)
    layers = [
        base.mark_line(color=LAST_MONTH, strokeWidth=2).encode(x=x, y=y),
        base.mark_point(filled=True, size=50, color=LAST_MONTH, stroke="white", strokeWidth=1.5).encode(
            x=x, y=y, tooltip=tooltip),
        base.transform_filter("datum.is_selected").mark_point(size=110, strokeWidth=2.5, color=ACCENT).encode(
            x=x, y=y, tooltip=tooltip,
            fill=alt.condition("datum.is_partial", alt.value("white"), alt.value(ACCENT))),
        base.transform_filter("datum.is_selected").mark_text(dy=-14, fontSize=11, fontWeight="bold",
                                                             color=INK).encode(x=x, y=y, text="text:N"),
    ]
    for name, value in references:
        ref = alt.Chart(pd.DataFrame({"value": [value], "name": [f"{name} {short_brl(value)}"]}))
        dash = [1, 3] if name == "Target" else [6, 4]
        colour = INK if name == "Target" else MUTED
        layers.insert(0, ref.mark_rule(color=colour, strokeDash=dash, strokeWidth=1.2).encode(
            y=alt.Y("value:Q"), tooltip=[alt.Tooltip("name:N", title=" ")]))
        layers.append(ref.mark_text(align="right", baseline="bottom", dy=-3, fontSize=11, color=MUTED).encode(
            y=alt.Y("value:Q"), x=alt.value("width"), text="name:N"))
    return finish(alt.layer(*layers), 300)
