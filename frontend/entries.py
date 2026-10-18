"""
The Entries page's shaping: every expense you can see (GET
/expenditures/) as a table to audit, its filters, the trace of each edit,
and an expense's values for the edit form.

No Streamlit import, so it's unit-tested in tests/test_entries.py.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd

from money import format_brl

# How a payment method stored without an institution is shown and matched.
NO_INSTITUTION = "N/A"
# A pet-category expense with no pet_id was for all the pets.
ALL_PETS = "Both"
KINDS = {"all": "Everything", "shared": "Shared", "personal": "Personal"}
TABLE_COLUMNS = ["When", "What", "Price", "Your part", "Paid with", "Type", "Logged by", "Last edit"]


def local(value: str, tz) -> datetime.datetime:
    """An API timestamp in São Paulo time (a naive one is UTC)."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(tz).to_pydatetime()


def name_of(user: dict | None) -> str:
    return (user or {}).get("full_name") or (user or {}).get("email") or "—"


def kind_text(e: dict) -> str:
    """'Shared', 'Personal', 'Shared · treat', 'Shared · 10x'."""
    text = "Shared" if e.get("is_shared") else "Personal"
    if e.get("is_treat"):
        text += " · treat"
    total = e.get("total_installments") or 1
    return f"{text} · {total}x" if total > 1 else text


def what_text(e: dict) -> str:
    """'Food · Groceries', and the pet for a pet category: 'Pets · Vet · Thor' (or '· Both')."""
    category = e.get("category") or {}
    text = f"{category.get('primary_category', '—')} · {category.get('sub_category', '—')}"
    if category.get("for_pets"):
        text += f" · {(e.get('pet') or {}).get('name') or ALL_PETS}"
    return text


def paid_with(e: dict) -> str:
    method = e.get("payment_method") or {}
    bank = method.get("institution")
    return f"{method.get('method_name', '—')} · {bank}" if bank else method.get("method_name", "—")


def edit_text(e: dict, tz) -> str:
    """'bob · 18/10 14:02' for the last edit, '' when never edited."""
    if not e.get("updated_at"):
        return ""
    when = local(e["updated_at"], tz)
    who = name_of(e.get("updated_by")) if e.get("updated_by") else "a deleted account"
    return f"{who} · {when:%d/%m %H:%M}"


def trace_text(e: dict, tz) -> str:
    """Who logged it, and who last changed it and when, in a sentence."""
    logged = f"Logged by {name_of(e.get('user'))}."
    if not e.get("updated_at"):
        return logged + " Never edited."
    when = local(e["updated_at"], tz)
    who = name_of(e.get("updated_by")) if e.get("updated_by") else "an account since deleted"
    return f"{logged} Last edited by {who} on {when.day} {when:%B} at {when:%H:%M}."


def entries_frame(expenses: list[dict] | None, tz) -> pd.DataFrame:
    """
    One row per expense, newest first: the display columns (TABLE_COLUMNS,
    money as text) plus what the filters read: id, month (YYYY-MM), kind
    (shared/personal), primary category and who logged it.
    """
    rows = []
    for e in expenses or []:
        when = local(e["transaction_timestamp"], tz)
        rows.append({
            "id": e["expenditure_id"], "at": when, "month": when.strftime("%Y-%m"),
            "kind": "shared" if e.get("is_shared") else "personal",
            "primary": (e.get("category") or {}).get("primary_category", "—"),
            "logged_by": name_of(e.get("user")),
            "price_value": float(e["price"]), "mine_value": float(e.get("my_share") or 0),
            "When": when.strftime("%d/%m/%Y %H:%M"), "What": what_text(e),
            "Price": format_brl(e["price"]), "Your part": format_brl(e.get("my_share") or 0),
            "Paid with": paid_with(e), "Type": kind_text(e), "Logged by": name_of(e.get("user")),
            "Last edit": edit_text(e, tz),
        })
    if not rows:
        return pd.DataFrame(columns=["id", "at", "month", "kind", "primary", "logged_by", "price_value",
                                     "mine_value", *TABLE_COLUMNS])
    return pd.DataFrame(rows).sort_values(["at", "id"], ascending=False, ignore_index=True)


def filter_entries(df: pd.DataFrame, month: str | None = None, kind: str = "all", logged_by: str | None = None,
                   categories: list[str] | None = None, search: str = "") -> pd.DataFrame:
    """The rows matching every filter given; `search` looks in what, how it was paid and the price."""
    out = df
    if month:
        out = out[out["month"] == month]
    if kind != "all":
        out = out[out["kind"] == kind]
    if logged_by:
        out = out[out["logged_by"] == logged_by]
    if categories:
        out = out[out["primary"].isin(categories)]
    text = search.strip().lower()
    if text:
        haystack = (out["What"] + " " + out["Paid with"] + " " + out["Price"]).str.lower()
        out = out[haystack.str.contains(text, regex=False)]
    return out.reset_index(drop=True)


def summary(df: pd.DataFrame) -> str:
    """'12 expenses · R$ 1.234,00 · your part R$ 700,00'."""
    n = len(df)
    noun = "expense" if n == 1 else "expenses"
    return f"{n} {noun} · {format_brl(df['price_value'].sum())} · your part {format_brl(df['mine_value'].sum())}"


def form_values(e: dict, pets: list[dict] | None, tz, names: dict[int, str] | None = None) -> dict:
    """
    An expense from GET /expenditures/ as the edit form's starting values:
    the price as typed ("1.234,56"), payment method and institution,
    installments, category, the pet (a name or ALL_PETS, only when the
    form asks: two or more pets), shared, treat, the split (`custom`
    {user_id: percent} for a manual one, else None; `split` the stored
    (user_id, share_pct) pairs and `split_text` them in words), nature,
    date and time.
    """
    when = local(e["transaction_timestamp"], tz)
    method = e.get("payment_method") or {}
    category = e.get("category") or {}
    splits = e.get("splits") or []
    names = names or {}
    pet = None
    if category.get("for_pets") and len(pets or []) > 1:
        pet = (e.get("pet") or {}).get("name") or ALL_PETS
    manual = any(s.get("split_source") == "manual" for s in splits)
    split = [(s["user_id"], Decimal(str(s["share_pct"]))) for s in splits]
    return {
        "price_text": format_brl(e["price"], symbol=False),
        "method": method.get("method_name"),
        "institution": method.get("institution") or NO_INSTITUTION,
        "total_installments": e.get("total_installments") or 1,
        "current_installment": e.get("current_installment") or 1,
        "primary": category.get("primary_category"),
        "sub": category.get("sub_category"),
        "pet": pet,
        "shared": bool(e.get("is_shared")),
        "was_shared": bool(e.get("is_shared")),
        "treat": bool(e.get("is_treat")),
        "custom": {uid: int(round(float(pct) * 100)) for uid, pct in split} if manual else None,
        "split": split,
        "split_text": " · ".join(f"{names.get(uid, f'user {uid}')} {float(pct):.0%}" for uid, pct in split),
        "nature": e.get("nature") or "Normal",
        "date": when.date(),
        "time": when.time().replace(second=0, microsecond=0),
    }
