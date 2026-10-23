"""
In-app notices for the month in progress: a category past its monthly
target, one close to it with days still to go, and a recurring bill whose
usual day has passed without it being logged. Shown at the top of This
month, never pushed to a phone.

Pure: tested in tests/test_notices.py.
"""
from __future__ import annotations

import pandas as pd

from joint_shaping import ordinal
from money import format_brl

NEAR = 0.9  # "close to its target" from 90% of it


def notices(targets: dict[str, float], spent: dict[str, float], due: pd.DataFrame, day: int,
            days: int) -> list[tuple[str, str | None]]:
    """
    (text, tone) lines, the most urgent first: categories past their target
    (tone "more"), then those within 10% of it with days to go, then
    recurring bills (`due`, from upcoming.recurring_due) whose usual day is
    before today. `spent` is this month so far by primary category.
    """
    over, near = [], []
    for name, target in targets.items():
        if target <= 0:
            continue
        value = spent.get(name, 0.0)
        ratio = value / target
        if ratio > 1:
            over.append((ratio, f"{name} is past its monthly target: {format_brl(value)} of {format_brl(target)}.",
                         "more"))
        elif ratio >= NEAR and day < days:
            near.append((ratio, f"{name} is at {ratio:.0%} of its monthly target with {days - day} days to go.",
                         None))
    late = []
    if not due.empty:
        for _, bill in due.sort_values("day").iterrows():
            if bill["day"] < day:
                late.append((f"{bill['name'].split(' › ')[-1]} ({format_brl(bill['amount'])}) usually comes by the "
                             f"{ordinal(int(bill['day']))} and isn't logged yet.", None))
    return ([(t, tone) for _, t, tone in sorted(over, reverse=True)]
            + [(t, tone) for _, t, tone in sorted(near, reverse=True)] + late)
