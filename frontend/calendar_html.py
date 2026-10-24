"""
This month's calendar as plain HTML: a CSS grid of day squares (weeks
down, Monday first), each shaded by what was spent. HTML rather than a
chart so the squares keep their shape at any width, the card sizes itself,
and a phone gets bigger squares instead of a squeezed chart. Styled by the
.hf-cal rules in ui.py; pure, so the markup is testable.
"""
from html import escape

import pandas as pd

from daily_charts import EMPTY_DAY, HEAT, INK

WEEKDAY_LETTERS = ["M", "T", "W", "T", "F", "S", "S"]
WHITE_FROM = 0.55  # share of the scale above which a day's number turns white


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def shade(amount: float, top: float) -> str:
    """
    A day's colour: pale grey with nothing spent, then from the lightest
    green to brand green at `top` or more (daily_shaping.calendar_scale_max,
    a typical big day, so one rent payment doesn't wash the rest out).
    """
    if amount <= 0:
        return EMPTY_DAY
    t = min(amount / max(top, 1.0), 1.0)
    (r1, g1, b1), (r2, g2, b2) = _rgb(HEAT[0]), _rgb(HEAT[1])
    return "#{:02x}{:02x}{:02x}".format(round(r1 + (r2 - r1) * t), round(g1 + (g2 - g1) * t), round(b1 + (b2 - b1) * t))


def day_title(row) -> str:
    """The hover text: 'Fri 23 October · R$ 305,00 · 3 expenses · mostly Food'."""
    if row["state"] == "future":
        return row["label"]
    parts = [row["label"], row["amount_brl"]]
    if row["count"]:
        parts.append(f"{row['count']} expense{'s' if row['count'] != 1 else ''}")
    if row["top_category"]:
        parts.append(f"mostly {row['top_category']}")
    return " · ".join(parts)


def calendar_html(cal: pd.DataFrame, top: float) -> str:
    """
    The grid for daily_shaping.calendar_frame rows. The 1st starts in its
    weekday's column (grid-column), so no blank cells are needed; today is
    outlined and days to come are blank squares.
    """
    head = "".join(f'<div class="hf-cal-head">{d}</div>' for d in WEEKDAY_LETTERS)
    cells = []
    for _, row in cal.iterrows():
        classes = ["hf-cal-day", f"hf-{row['state']}"]
        style = []
        if row["day"] == 1:
            style.append(f"grid-column:{int(row['weekday']) + 1}")
        if row["state"] != "future":
            style.append(f"background:{shade(row['amount'], top)}")
            dark = row["amount"] > top * WHITE_FROM
            style.append(f"color:{'#ffffff' if dark else INK}")
        cells.append(f'<div class="{" ".join(classes)}" style="{";".join(style)}" '
                     f'title="{escape(day_title(row))}">{int(row["day"])}</div>')
    return f'<div class="hf-cal">{head}{"".join(cells)}</div>'
