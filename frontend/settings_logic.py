"""
Turns an edited Settings table into the API calls that apply it.

The Settings page shows categories and payment methods as editable tables
(st.data_editor): edit a cell to rename, type in the last row to add, select
rows and press Delete to remove. `plan_changes` compares the table before
and after and returns what to send, plus any reason it can't be saved yet,
so the page can show the plan before anything is written. Pure, so it is
tested without Streamlit.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Table:
    """How one dimension maps onto its editable table."""
    key: str                 # the id field, e.g. "category_id"
    fields: tuple            # editable API fields, in column order
    required: tuple          # fields that can't be blank
    unique: tuple            # fields that together must be unique
    label: callable          # row dict -> human label, e.g. "Food › Groceries"
    choices: dict = field(default_factory=dict)  # field -> allowed values
    flags: dict = field(default_factory=dict)    # tick-box field -> (on, off) wording


CATEGORIES = Table(
    key="category_id",
    fields=("primary_category", "sub_category", "cost_type", "for_pets"),
    required=("primary_category", "sub_category", "cost_type"),
    unique=("primary_category", "sub_category"),
    label=lambda r: f"{r['primary_category']} › {r['sub_category']}",
    choices={"cost_type": ("Variable", "Fixed")},
    flags={"for_pets": ("asks which pet", "doesn't ask which pet")},
)

PAYMENT_METHODS = Table(
    key="payment_method_id",
    fields=("method_name", "institution", "is_credit", "is_joint"),
    required=("method_name",),
    unique=("method_name", "institution"),
    label=lambda r: f"{r['method_name']}{' · ' + r['institution'] if r.get('institution') else ''}",
    flags={
        "is_credit": ("credit (offers installments)", "not credit"),
        "is_joint": ("a joint account (nobody owes for it)", "a personal account"),
    },
)

PETS = Table(
    key="pet_id",
    fields=("name",),
    required=("name",),
    unique=("name",),
    label=lambda r: r["name"],
)


@dataclass
class Plan:
    adds: list = field(default_factory=list)      # payloads to POST
    updates: list = field(default_factory=list)   # (id, changed fields) to PATCH
    deletes: list = field(default_factory=list)   # ids to DELETE
    lines: list = field(default_factory=list)     # one plain sentence per change
    errors: list = field(default_factory=list)    # why it can't be saved yet

    @property
    def empty(self) -> bool:
        return not (self.adds or self.updates or self.deletes)


def clean(value):
    """Blank cells come back as None, NaN or ""; text is trimmed."""
    if value is None or value != value:  # NaN is the only value unequal to itself
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def normalise(row: dict, table: Table) -> dict:
    out = {f: clean(row.get(f)) for f in table.fields}
    for flag in table.flags:
        out[flag] = bool(out[flag])  # a new row's untouched tick box is None
    return out


def plan_changes(original: list[dict], edited: list[dict], table: Table) -> Plan:
    """
    `original` is what the API returned (each row has the id and
    `expense_count`); `edited` is the table's rows afterwards, where rows the
    person added have no id.
    """
    plan = Plan()
    before = {r[table.key]: r for r in original}
    kept_ids = set()
    final_rows = []

    for raw in edited:
        row_id = clean(raw.get(table.key))
        row = normalise(raw, table)
        if all(row[f] in (None, False) for f in table.fields):
            continue  # an empty row the editor added but nobody filled in
        missing = [f for f in table.required if row[f] is None]
        bad = [f for f, allowed in table.choices.items() if row[f] is not None and row[f] not in allowed]
        if missing or bad:
            plan.errors.append(f"Fill in every column for “{table.label(fill_blanks(row))}”.")
            continue
        final_rows.append(row)

        if row_id is None:
            plan.adds.append(row)
            plan.lines.append(f"Add {table.label(row)}")
            continue
        row_id = int(row_id)
        kept_ids.add(row_id)
        old = normalise(before[row_id], table)
        changes = {f: row[f] for f in table.fields if row[f] != old[f]}
        if changes:
            plan.updates.append((row_id, changes))
            plan.lines.append(describe_update(old, row, table))

    for row_id, old in before.items():
        if row_id in kept_ids:
            continue
        name = table.label(normalise(old, table))
        used = old.get("expense_count", 0)
        if used:
            plan.errors.append(
                f"{name} can't be removed: {used} expense{'s' if used != 1 else ''} use it. "
                "Rename it instead, or delete those expenses first."
            )
        else:
            plan.deletes.append(row_id)
            plan.lines.append(f"Remove {name}")

    seen = {}
    for row in final_rows:
        k = tuple((row[f] or "").lower() for f in table.unique)
        if k in seen:
            plan.errors.append(f"{table.label(row)} appears twice.")
        seen[k] = True

    return plan


def fill_blanks(row: dict) -> dict:
    return {k: ("…" if v is None else v) for k, v in row.items()}


def describe_update(old: dict, new: dict, table: Table) -> str:
    before, after = table.label(old), table.label(new)
    rest = [f for f in table.fields if old[f] != new[f] and f not in table.unique]
    parts = []
    if before != after:
        parts.append(f"Rename {before} → {after}")
    for f in rest:
        value = new[f]
        if f in table.flags:
            on, off = table.flags[f]
            parts.append(f"{after}: {on if value else off}")
        else:
            parts.append(f"{after}: {f.replace('_', ' ')} → {value}")
    return "; ".join(parts)


def household_payload(shares_pct: dict[int, float]) -> tuple[list[dict], str | None]:
    """
    The Household split as typed (user_id -> percent, 0 = not in the
    household) to the PUT body, or an error message. Percent to a fraction
    with four decimals, as household_setting stores it.
    """
    members = {uid: pct for uid, pct in shares_pct.items() if pct and pct > 0}
    total = sum(members.values())
    if not members:
        return [], "Give at least one person a share."
    if abs(total - 100) >= 0.01:
        return [], f"Shares must add up to 100% (now {total:g}%)."
    return [{"user_id": uid, "share_pct": round(pct / 100, 4)} for uid, pct in members.items()], None


# --- Monthly targets ------------------------------------------------------------

def suggest_targets(analytics: dict | None, n: int = 3, step: int = 50) -> tuple[dict[str, float], list[str]]:
    """
    A starting target per primary category from history: the average of
    the last `n` months logged in full before this one (shared spending at
    full price, from an /analytics/shared payload whose window ends last
    month), rounded up to the next R$ `step`. Returns the suggestions and
    the months they average (fewer than `n` while history is short; none
    before a whole month has been logged).
    """
    import math

    import analytics_shaping as shape

    if not analytics or not analytics.get("rows"):
        return {}, []
    df = shape.to_frame(analytics)
    since = shape.tracked_since(analytics.get("first_date")) or df["month"].min()
    months = [m for m in analytics["months"] if m >= since][-n:]
    if not months:
        return {}, []
    totals = df[df["month"].isin(months)].groupby("primary_category")["household"].sum()
    suggested = {c: float(math.ceil(v / len(months) / step) * step) for c, v in totals.items() if v > 0}
    return suggested, months


def target_rows(categories: list[dict], targets: list[dict], suggested: dict[str, float] | None = None,
                fill_blanks: bool = False) -> "pd.DataFrame":
    """
    One row per primary category, A–Z: `Category`, its `Target` as typed
    text ("3.000,00"; blank = no target) and the `Suggested` one from
    history (suggest_targets), for Settings' targets table. With
    `fill_blanks`, a blank target starts at its suggestion, to review
    before saving.
    """
    import pandas as pd
    from money import format_brl

    suggested = suggested or {}
    current = {t["primary_category"]: t["amount"] for t in targets or []}
    names = sorted({c["primary_category"] for c in categories or []}, key=str.lower)

    def target(n):
        if n in current:
            return format_brl(current[n], symbol=False)
        return format_brl(suggested[n], symbol=False) if fill_blanks and n in suggested else ""

    return pd.DataFrame({"Category": names, "Target": [target(n) for n in names],
                         "Suggested": [format_brl(suggested[n]) if n in suggested else "—" for n in names]})


def targets_payload(edited: "pd.DataFrame") -> tuple[list[dict], list[str]]:
    """
    The edited targets table as PUT /category_targets/'s list (blank rows
    left out: no target), and the errors that block saving, in words.
    """
    from money import parse_brl

    targets, errors = [], []
    for name, text in zip(edited["Category"], edited["Target"].fillna("")):  # "Suggested" is only a hint
        text = str(text).strip()
        if not text:
            continue
        try:
            amount = parse_brl(text)
        except ValueError as e:
            errors.append(f"{name}: {e}")
            continue
        if amount <= 0:
            errors.append(f"{name}: a target must be more than zero (leave it blank for none).")
            continue
        targets.append({"primary_category": name, "amount": str(amount)})
    return targets, errors
