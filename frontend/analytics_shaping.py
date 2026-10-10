"""
Shaping /analytics/shared responses for the Analytics Overview.

Pure pandas, no Streamlit import, so it's unit-tested in
frontend/tests/test_analytics_shaping.py and the page stays thin.

Amounts arrive as decimal strings and become floats here: Altair needs
plain numbers, and every figure shown goes back through money.format_brl,
which rounds to the cent. Sums are rounded to two places as they're made.

Two lenses on the same shared expenses: "household" (the full price) and
"mine" (the logged-in user's share_amount). A month in progress is compared
with the same days of other months via the *_to_day columns.
"""
from __future__ import annotations

import math

import pandas as pd

from money import format_brl

LENSES = {"Household": "household", "My share": "mine"}
AMOUNT_COLUMNS = ["household", "mine", "household_to_day", "mine_to_day"]
ROW_COLUMNS = ["month", "primary_category", "sub_category", "cost_type", *AMOUNT_COLUMNS, "count"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Vega expression for a money axis: 1234 -> "R$ 1.234" (Brazilian grouping).
BRL_AXIS_EXPR = "'R$ ' + replace(format(datum.value, ',.0f'), regexp(',', 'g'), '.')"


# --- months -------------------------------------------------------------

def shift_month(month: str, delta: int) -> str:
    """'2026-10', -1 -> '2026-09'; crosses year boundaries."""
    index = int(month[:4]) * 12 + int(month[5:]) - 1 + delta
    return f"{index // 12}-{index % 12 + 1:02d}"


def month_options(current: str, n: int = 12) -> list[str]:
    """The last n months ending at `current`, newest first (for a picker)."""
    return [shift_month(current, -k) for k in range(n)]


def month_label(month: str, short: bool = False) -> str:
    """'2026-10' -> 'Oct 2026', or 'Oct 26' when short."""
    name = MONTH_NAMES[int(month[5:]) - 1]
    return f"{name} {month[2:4]}" if short else f"{name} {month[:4]}"


# --- the response as a frame --------------------------------------------

def to_frame(payload: dict | None) -> pd.DataFrame:
    """The response's rows as a DataFrame with float amounts (empty but typed when there are none)."""
    rows = (payload or {}).get("rows") or []
    df = pd.DataFrame(rows, columns=ROW_COLUMNS)
    for col in AMOUNT_COLUMNS:
        df[col] = pd.to_numeric(df[col]).astype(float)
    df["count"] = pd.to_numeric(df["count"]).fillna(0).astype(int)
    return df


def lens_column(lens: str, to_day: bool = False) -> str:
    """'Household' -> 'household'; with to_day, the same-days column."""
    col = LENSES.get(lens, lens)
    return f"{col}_to_day" if to_day else col


def monthly_totals(df: pd.DataFrame, months: list[str], lens: str, to_day: bool = False) -> pd.Series:
    """Total per month over `months`, zero-filled, in window order."""
    col = lens_column(lens, to_day)
    totals = df.groupby("month")[col].sum() if not df.empty else pd.Series(dtype=float)
    return totals.reindex(months, fill_value=0.0).astype(float).round(2)


def expense_count(df: pd.DataFrame, month: str) -> int:
    return int(df.loc[df["month"] == month, "count"].sum())


# --- comparisons --------------------------------------------------------

def _pct(change: float, previous: float) -> float:
    """Relative change, or NaN when there's nothing to compare with."""
    return change / previous if previous > 0 else math.nan


def compare(df: pd.DataFrame, selected: str, is_partial: bool, lens: str,
            by: str = "primary_category", where: dict | None = None) -> pd.DataFrame:
    """
    The selected month against the previous one, per `by` value.

    The selected month counts everything logged in it; the previous month
    counts only the same days when the selected month is still in progress.
    Returns columns [by, current, previous, change, pct], largest current first;
    pct is NaN when the previous value is zero.
    """
    previous = shift_month(selected, -1)
    d = df
    for column, value in (where or {}).items():
        d = d[d[column] == value]
    current = d[d["month"] == selected].groupby(by)[lens_column(lens)].sum()
    before = d[d["month"] == previous].groupby(by)[lens_column(lens, to_day=is_partial)].sum()

    out = pd.DataFrame({"current": current, "previous": before}).fillna(0.0).astype(float).round(2)
    out = out[(out["current"] != 0) | (out["previous"] != 0)]
    out["change"] = (out["current"] - out["previous"]).round(2)
    out["pct"] = [_pct(c, p) for c, p in zip(out["change"], out["previous"])]
    out = out.rename_axis(by).reset_index()
    return out.sort_values(["current", by], ascending=[False, True], ignore_index=True)


def compare_total(df: pd.DataFrame, selected: str, is_partial: bool, lens: str) -> dict:
    """The selected month's total against the previous month (same days if partial)."""
    previous = shift_month(selected, -1)
    current = round(float(df.loc[df["month"] == selected, lens_column(lens)].sum()), 2)
    before = round(float(df.loc[df["month"] == previous, lens_column(lens, to_day=is_partial)].sum()), 2)
    change = round(current - before, 2)
    return {"current": current, "previous": before, "change": change, "pct": _pct(change, before)}


def previous_full_average(df: pd.DataFrame, months: list[str], selected: str, lens: str,
                          n: int = 3, to_day: bool = False) -> float | None:
    """
    Average of the n complete months just before `selected` (zero months
    count as zero), or None until n such months exist: all inside the
    window and none before the first month with any shared expense.
    With to_day, averages only the same days of each month.
    """
    wanted = [shift_month(selected, -k) for k in range(1, n + 1)]
    if df.empty or any(m not in months for m in wanted) or min(wanted) < df["month"].min():
        return None
    totals = monthly_totals(df, months, lens, to_day)
    return round(float(totals[wanted].mean()), 2)


def biggest_increase(comparison: pd.DataFrame, by: str = "primary_category") -> str | None:
    """The category whose spending rose most in R$, or None if nothing rose."""
    if comparison.empty or comparison["change"].max() <= 0:
        return None
    return comparison.sort_values(["change", by], ascending=[False, True]).iloc[0][by]


def biggest_changes(comparison: pd.DataFrame, by: str = "primary_category") -> pd.DataFrame:
    """Rows that changed, largest absolute change first."""
    changed = comparison[comparison["change"] != 0].copy()
    changed["_abs"] = changed["change"].abs()
    return changed.sort_values(["_abs", by], ascending=[False, True], ignore_index=True).drop(columns="_abs")


def heatmap_frame(df: pd.DataFrame, months: list[str], lens: str) -> pd.DataFrame:
    """
    Long form [primary_category, month, amount] for every category × month
    in the window, zero-filled; categories ordered by window total, largest first.
    """
    d = df[df["month"].isin(months)]
    if d.empty:
        return pd.DataFrame(columns=["primary_category", "month", "amount"])
    pivot = d.pivot_table(index="primary_category", columns="month", values=lens_column(lens),
                          aggfunc="sum", fill_value=0.0).reindex(columns=months, fill_value=0.0)
    order = pivot.sum(axis=1).sort_values(ascending=False, kind="stable").index
    long = pivot.loc[order].round(2).reset_index().melt(id_vars="primary_category", var_name="month", value_name="amount")
    long["amount"] = long["amount"].astype(float)
    return long


def cost_type_split(df: pd.DataFrame, selected: str, is_partial: bool, lens: str) -> pd.DataFrame:
    """compare() by cost type, plus each type's share of its month's total."""
    out = compare(df, selected, is_partial, lens, by="cost_type")
    for col in ("current", "previous"):
        total = out[col].sum()
        out[f"{col}_share"] = out[col] / total if total else 0.0
    return out


# --- text ---------------------------------------------------------------

def signed_brl(value: float) -> str:
    """12.5 -> '+R$ 12,50'; -3 -> '-R$ 3,00'; 0 -> 'R$ 0,00'."""
    text = format_brl(value)
    return f"+{text}" if round(value, 2) > 0 else text


def pct_text(pct: float) -> str:
    """0.125 -> '+12,5%'; NaN -> 'new'."""
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        return "new"
    return f"{pct * 100:+.1f}%".replace(".", ",")


def delta_text(change: float, pct: float) -> str:
    """'+R$ 12,50 (+5,0%)', or '+R$ 50,00 (new)' when there was nothing before."""
    return f"{signed_brl(change)} ({pct_text(pct)})"


def short_brl(value: float) -> str:
    """Compact amount for chart labels: 'R$ 812', 'R$ 1,2 mil', 'R$ 1,5 mi'."""
    amount = abs(value)
    sign = "-" if value < 0 else ""
    if amount >= 1_000_000:
        text = f"{amount / 1_000_000:.1f} mi"
    elif amount >= 1_000:
        text = f"{amount / 1_000:.1f} mil"
    else:
        return f"{sign}R$ {amount:.0f}"
    return f"{sign}R$ {text.replace('.', ',')}"
