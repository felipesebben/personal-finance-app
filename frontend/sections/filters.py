"""
The filter row every analysis view opens with (filtering.py does the
narrowing). On My expenses it starts with "Show": everything I spent,
personal only or my share of shared, which decides what's fetched, so it's
read first (`view()`) and the rest, which needs the categories from the
data, after (`filters()`).
"""
from __future__ import annotations

import streamlit as st

import filtering

# What My expenses can show: everything I spent, or one half of it.
VIEWS = {
    "all": "Everything I spent",
    "personal": "Personal only",
    "shared": "My share of shared",
}


class FilterRow:
    """
    One row of filters, keyed `<prefix>_view/_focus/_categories/_one_offs`.
    Defaults go through session state (not `default=`) so a test can
    preset them.
    """

    def __init__(self, prefix: str, show_view: bool = False):
        self.prefix = prefix
        self.show_view = show_view
        st.session_state.setdefault(f"{prefix}_focus", filtering.EVERYTHING)
        widths = [2, 2, 3, 2] if show_view else [2, 3, 2]
        self.cols = iter(st.columns(widths, vertical_alignment="bottom"))

    def view(self) -> str | None:
        """"all", "personal" or "shared" (None without the Show control)."""
        if not self.show_view:
            return None
        st.session_state.setdefault(f"{self.prefix}_view", "all")
        return next(self.cols).segmented_control(
            "Show", list(VIEWS), format_func=VIEWS.get, key=f"{self.prefix}_view",
            help="Everything I spent = my share of shared expenses + my personal ones.",
        ) or "all"

    def filters(self, categories: list[str]) -> filtering.Filters:
        prefix = self.prefix
        focus = next(self.cols).segmented_control(
            "What to count", filtering.FOCUSES, key=f"{prefix}_focus",
            help="Day-to-day = variable costs (groceries, delivery, fuel…), the ones a decision this week can "
                 "change. Fixed costs = rent, insurance, subscriptions. A category's type is set in Settings.",
        ) or filtering.EVERYTHING
        # A pick from another month's categories would make the multiselect fail: drop it first.
        chosen = f"{prefix}_categories"
        if chosen in st.session_state:
            st.session_state[chosen] = [c for c in st.session_state[chosen] if c in categories]
        picked = next(self.cols).multiselect("Categories", categories, key=f"{prefix}_categories",
                                             placeholder="All categories")
        without = next(self.cols).toggle("Leave out one-offs", key=f"{prefix}_one_offs",
                                         help="Expenses marked Annual or Extraordinary, like IPVA or a repair, "
                                              "which would make one month look expensive.")
        return filtering.Filters(focus, tuple(picked), without)
