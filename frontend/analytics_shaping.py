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
ROW_COLUMNS = ["month", "primary_category", "sub_category", "cost_type", "nature", *AMOUNT_COLUMNS, "count", "source"]
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
    df["nature"] = df["nature"].fillna("Normal")
    df["source"] = df["source"].fillna("")
    for col in AMOUNT_COLUMNS:
        df[col] = pd.to_numeric(df[col]).astype(float)
    df["count"] = pd.to_numeric(df["count"]).fillna(0).astype(int)
    return df


def merge_payloads(by_source: dict[str, dict]) -> dict:
    """
    Several /analytics (or /analytics/.../daily) payloads for the same
    window as one, each row tagged with its `source` (e.g. "shared",
    "personal") so a view can keep some of them.
    """
    payloads = {source: p for source, p in by_source.items() if isinstance(p, dict)}  # anything else: no rows
    merged = dict(next(iter(payloads.values()), {}))
    merged["rows"] = [{**row, "source": source} for source, p in payloads.items() for row in p.get("rows") or []]
    # Logging began with the first expense of any of them.
    firsts = [p["first_date"] for p in payloads.values() if p.get("first_date")]
    merged["first_date"] = min(firsts) if firsts else None
    return merged


# --- months logged in full ----------------------------------------------------

TRACKED_BY_DAY = 7  # a month counts as logged in full when logging had begun by its 7th (as daily_shaping)


def tracked_since(first_date: str | None) -> str | None:
    """
    The first month logged in full, from the payload's `first_date` (when
    logging began): that month if it began by the 7th, else the month after.
    Earlier months are never used for a ▲/▼ verdict.
    """
    if not first_date:
        return None
    month = first_date[:7]
    return month if int(first_date[8:10]) <= TRACKED_BY_DAY else shift_month(month, 1)


def partly_logged_from(month: str, first_date: str | None) -> int | None:
    """The day logging began in `month` when it began there after the 7th (a month logged in part), else None."""
    if not first_date or first_date[:7] != month or int(first_date[8:10]) <= TRACKED_BY_DAY:
        return None
    return int(first_date[8:10])


def ordinal(n: int) -> str:
    """1 -> '1st', 26 -> '26th'."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def with_share_text(frame: pd.DataFrame) -> pd.DataFrame:
    """ranked_comparison() bars when there's no fair comparison: the tip says the share, "R$ 4,1 mil · 59%"."""
    total = frame["amount"].sum()
    return frame.assign(text=[f"{short_brl(a)} · {a / total:.0%}" if total else short_brl(a)
                              for a in frame["amount"]])


def keep_sources(df: pd.DataFrame, sources: list[str] | None) -> pd.DataFrame:
    """The rows from these sources (all of them for None)."""
    return df if sources is None or df.empty else df[df["source"].isin(sources)]


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
                          n: int = 3, to_day: bool = False, since: str | None = None) -> float | None:
    """
    Average of the n complete months just before `selected` (zero months
    count as zero), or None until n such months exist: all inside the
    window, none before the first month with any shared expense, and none
    before `since` (the first month logged in full, tracked_since).
    With to_day, averages only the same days of each month.
    """
    wanted = [shift_month(selected, -k) for k in range(1, n + 1)]
    if df.empty or any(m not in months for m in wanted) or min(wanted) < df["month"].min():
        return None
    if since is not None and min(wanted) < since:
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


# --- charts' frames -----------------------------------------------------------

def month_bars(values: pd.Series, selected: str, money: bool = True) -> pd.DataFrame:
    """
    A KPI card's sparkbars from a per-month series (index YYYY-MM, oldest
    first): label ("Oct"), value, value text and is_selected, the frame
    daily_charts.spark_bars draws.
    """
    out = pd.DataFrame({"month": list(values.index), "value": [float(v) for v in values.values]})
    out["label"] = [MONTH_NAMES[int(m[5:]) - 1] for m in out["month"]]
    out["value_brl"] = out["value"].map(format_brl) if money else out["value"].map(lambda v: f"{v:.0f}")
    out["is_selected"] = out["month"] == selected
    return out


def monthly_counts(df: pd.DataFrame, months: list[str]) -> pd.Series:
    """How many expenses per month over `months`, zero-filled."""
    counts = df.groupby("month")["count"].sum() if not df.empty else pd.Series(dtype=float)
    return counts.reindex(months, fill_value=0).astype(int)


def ranked_comparison(comparison: pd.DataFrame, by: str) -> pd.DataFrame:
    """
    compare() as ranked bars with a tick for the month before: name,
    amount (this month), previous, their text, and the text at the bar's
    tip, "R$ 4.135 · ▲ 12%" (or "new" when there was nothing before).
    """
    out = comparison.rename(columns={by: "name", "current": "amount"}).copy()
    out["amount_brl"] = out["amount"].map(format_brl)
    out["previous_brl"] = out["previous"].map(format_brl)

    def move(change: float, pct: float) -> str:
        if round(change, 2) == 0:
            return "same"
        arrow = "▲" if change > 0 else "▼"
        return "new" if math.isnan(pct) else f"{arrow} {abs(pct) * 100:.0f}%"

    out["text"] = [f"{short_brl(a)} · {move(c, p)}" for a, c, p in zip(out["amount"], out["change"], out["pct"])]
    return out


def as_changes(comparison: pd.DataFrame, by: str) -> pd.DataFrame:
    """compare() in the shape daily_charts.changes_chart draws: name, change, now/then/change text, direction."""
    changed = biggest_changes(comparison, by)
    return pd.DataFrame({
        "name": changed[by], "change": changed["change"],
        "now_brl": changed["current"].map(format_brl), "then_brl": changed["previous"].map(format_brl),
        "change_brl": [("▲ +" if c > 0 else "▼ ") + format_brl(c) for c in changed["change"]],
        "direction": ["more" if c > 0 else "less" for c in changed["change"]],
    })


# --- what we control, fixed costs, one-offs ------------------------------------

ONE_OFFS = ("Annual", "Extraordinary")  # as filtering.ONE_OFFS
ABOVE = 1.10  # "above usual": more than 10% over it


def controllable(df: pd.DataFrame) -> pd.DataFrame:
    """Spending that depends on how we live: cost type Variable (bills that vary included), one-offs left out."""
    return df[(df["cost_type"] == "Variable") & ~df["nature"].isin(ONE_OFFS)]


def fixed_costs(df: pd.DataFrame) -> pd.DataFrame:
    """Fixed costs that recur (rent, internet, subscriptions), one-offs left out."""
    return df[(df["cost_type"] == "Fixed") & ~df["nature"].isin(ONE_OFFS)]


def one_offs(df: pd.DataFrame) -> pd.DataFrame:
    """Annual and extraordinary costs: the surprises and the once-a-year bills."""
    return df[df["nature"].isin(ONE_OFFS)]


def usual_before(totals: pd.Series, month: str, since: str | None, n: int = 3) -> float | None:
    """
    The usual month before `month`: the average of up to `n` months before
    it that were logged in full (from `since`), from a per-month series;
    None before any. Fewer than `n` while history is short, so "usual" can
    be said from the first whole month on.
    """
    before = [m for m in totals.index if m < month and (since is None or m >= since)][-n:]
    return round(float(totals[before].mean()), 2) if before else None


def control_rows(df: pd.DataFrame, months: list[str], selected: str, lens: str, is_partial: bool,
                 since: str | None, shown: int = 6) -> list[dict]:
    """
    "Are the costs we control changing?": per primary category of
    controllable() spending, biggest this month first: `current`, the
    `usual` month (same days while the month is going), `change` and `pct`
    against it, the last `shown` months (`series`, for sparkbars) and
    `streak`, how many months in a row up to this one were above their own
    usual (more than 10% over it: two or more is a habit, not a blip).
    """
    d = controllable(df)
    window = months[-shown:]
    out = []
    for name, rows in d.groupby("primary_category"):
        full = monthly_totals(rows, months, lens)
        to_day = monthly_totals(rows, months, lens, to_day=True)
        current = float(full.get(selected, 0.0))
        series = full[window]
        if not series.any():
            continue
        # This month against the same days of the usual month while it's going.
        usual = usual_before(to_day if is_partial else full, selected, since)
        streak = 0
        for m in [m for m in months if m <= selected][::-1]:
            base = usual_before(to_day if (m == selected and is_partial) else full, m, since)
            if base is None or float(full[m]) <= base * ABOVE:
                break
            streak += 1
        change = round(current - usual, 2) if usual is not None else None
        out.append({"name": name, "current": round(current, 2), "usual": usual, "change": change,
                    "pct": _pct(change, usual) if usual else math.nan, "series": series, "streak": streak})
    return sorted(out, key=lambda r: (-r["current"], r["name"]))


def control_lines(rows: list[dict]) -> list[tuple[str, str | None]]:
    """
    The control card's answer, in sentences (text, tone): what has been
    above usual for two months or more (losing control), where the most
    could be saved, or that everything is close to usual.
    """
    compared = [r for r in rows if r["usual"] is not None]
    if not compared:
        return [("The usual month appears once a whole month has been logged.", None)]
    lines = []
    habit = [r["name"] for r in compared if r["streak"] >= 2]
    if habit:
        lines.append((f"Above usual for two months or more: {_names(habit)}.", "more"))
    over = sorted((r for r in compared if r["usual"] and r["current"] > r["usual"] * ABOVE),
                  key=lambda r: -r["change"])[:3]
    if over:
        lines.append(("Where you could save: " + "; ".join(
            f"{r['name']} {format_brl(r['change'])} above usual" for r in over) + ".", None))
    if not lines:
        lines.append(("Everything you control is within 10% of usual.", "less"))
    return lines


def _names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


RESERVE_ROUND = 50   # the suggested monthly reserve, rounded up to R$ 50
RESERVE_SOLID = 6    # months logged in full before the reserve is more than a rough guess


def reserve(df: pd.DataFrame, months: list[str], selected: str, lens: str, since: str | None) -> dict | None:
    """
    How much to set aside a month for one-offs: what annual and
    extraordinary costs averaged per month over the months logged in full
    before `selected` (`monthly`, rounded up to R$ 50; `rough` while fewer
    than six), and the annual bills of the last year that come round again
    (`coming`: name, the month they're next due, what they cost last time),
    soonest first. None before a whole month has been logged.
    """
    import math

    full = [m for m in months if m < selected and (since is None or m >= since)]
    if not full:
        return None
    offs = one_offs(df)
    column = lens_column(lens)
    total = float(offs.loc[offs["month"].isin(full), column].sum())
    monthly = float(math.ceil(total / len(full) / RESERVE_ROUND) * RESERVE_ROUND)
    annual = offs[(offs["nature"] == "Annual") & offs["month"].isin(months)]
    last = annual.groupby(["sub_category", "month"])[column].sum().reset_index()
    last = last.sort_values("month").groupby("sub_category").tail(1)  # the latest time each was paid
    coming = sorted(((r["sub_category"], shift_month(r["month"], 12), round(float(r[column]), 2))
                     for _, r in last.iterrows() if r[column] > 0), key=lambda c: (c[1], c[0]))
    return {"monthly": monthly, "months": len(full), "rough": len(full) < RESERVE_SOLID, "coming": coming}


def reserve_lines(r: dict | None) -> list[tuple[str, str | None]]:
    """The reserve as the One-offs card says it, (text, tone)."""
    if r is None:
        return [("A reserve to set aside appears once a whole month has been logged.", None)]
    span = f"{r['months']} month{'s' if r['months'] != 1 else ''}"
    lines = [(f"Set aside about {format_brl(r['monthly'])} a month for them"
              + (f" (a rough guess from {span} logged)" if r["rough"] else f" (from the last {span})"), None)]
    for name, month, amount in r["coming"][:3]:
        lines.append((f"Coming round: {name} in {month_label(month, short=True)}, {format_brl(amount)} last time", None))
    return lines
