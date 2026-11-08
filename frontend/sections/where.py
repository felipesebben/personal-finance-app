"""
Where the money goes, as both analysis views draw it: ranked bars with
their change beside them (each row of the change lines up with its bar on
a wide screen; on a phone it follows underneath, named again), and the
picker for what's inside a category on its own row, above what it drives.
"""
from __future__ import annotations

import streamlit as st

import analytics_charts as charts
from analytics_shaping import short_brl

MODES = ["R$", "%"]


def change_mode(container, key: str) -> str:
    """'R$' or '%': how the change beside the bars is measured (% puts small and big categories on one scale)."""
    st.session_state.setdefault(key, "R$")
    return container.segmented_control("Change in", MODES, key=key,
                                       help="R$: how much more or less. %: against what it was, so small and "
                                            "big categories share one scale.") or "R$"


def bars_and_change(frame, mode: str, tick: str | None, picked: str | None = None, target: str | None = None,
                    room: float = 1.4, change_title: str = "Change") -> None:
    """
    The bars (with a grey tick at `tick` and a dark one at `target`) and,
    when there's a comparison, the change beside them. With the change drawn,
    the tip of a bar only says its amount.
    """
    if tick is None:
        st.altair_chart(charts.ranked_bars(frame, picked=picked, room=room + 0.3, target=target),
                        use_container_width=True)
        return
    frame = frame.assign(text=frame["amount"].map(short_brl))
    left, right = st.columns([3, 2], gap="medium")
    with left:
        st.altair_chart(charts.ranked_bars(frame, picked=picked, previous=tick, room=room, target=target),
                        use_container_width=True)
    with right:
        st.altair_chart(charts.change_bars(frame.assign(previous=frame[tick]), mode, change_title),
                        use_container_width=True)
