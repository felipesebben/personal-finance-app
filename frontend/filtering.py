"""
What a view counts: every analysis view (This month and Month by month, on
Our expenses and My expenses) can narrow its rows the same way before
adding anything up:

- what to count: everything, day-to-day costs (cost type Variable, the
  ones a decision this week can change) or fixed costs;
- some primary categories only;
- without one-offs (nature Annual or Extraordinary, like an IPVA or a
  repair, which make one month look expensive).

Works on any frame with primary_category, cost_type and nature columns:
the /analytics rows, the daily rows and a list of expenses. No Streamlit
import, so it's unit-tested; sections/filters.py draws the widgets.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

EVERYTHING, DAY_TO_DAY, FIXED = "Everything", "Day-to-day", "Fixed costs"
FOCUSES = [EVERYTHING, DAY_TO_DAY, FIXED]
FOCUS_COST_TYPE = {DAY_TO_DAY: "Variable", FIXED: "Fixed"}
ONE_OFFS = ("Annual", "Extraordinary")


@dataclass(frozen=True)
class Filters:
    focus: str = EVERYTHING
    categories: tuple[str, ...] = field(default_factory=tuple)
    without_one_offs: bool = False

    @property
    def active(self) -> bool:
        return self.focus != EVERYTHING or bool(self.categories) or self.without_one_offs


def filter_rows(rows: pd.DataFrame, filters: Filters | None = None) -> pd.DataFrame:
    """The rows the filters keep (all of them without filters)."""
    if filters is None or rows.empty or not filters.active:
        return rows
    keep = pd.Series(True, index=rows.index)
    if filters.focus in FOCUS_COST_TYPE:
        keep &= rows["cost_type"] == FOCUS_COST_TYPE[filters.focus]
    if filters.categories:
        keep &= rows["primary_category"].isin(filters.categories)
    if filters.without_one_offs:
        keep &= ~rows["nature"].isin(ONE_OFFS)
    return rows[keep]


def note(filters: Filters | None) -> str:
    """What's being counted, in a few words, or '' for everything: 'day-to-day costs · Food, Pets · without one-offs'."""
    if filters is None:
        return ""
    parts = []
    if filters.focus == DAY_TO_DAY:
        parts.append("day-to-day costs")
    elif filters.focus == FIXED:
        parts.append("fixed costs")
    if filters.categories:
        parts.append(", ".join(filters.categories))
    if filters.without_one_offs:
        parts.append("without one-offs")
    return " · ".join(parts)
