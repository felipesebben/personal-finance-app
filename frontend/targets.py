"""
The household's monthly targets (GET /category_targets/) as the views use
them. Pure, no Streamlit import; tests in tests/test_targets.py.

A target is for a whole primary category (`sub_category` null) or for one
sub-category of it, e.g. Pets › Grooming after deciding on half as many
sessions. The two stand apart: a sub-category's target is a decision to
follow, not a slice of its category's.
"""
from __future__ import annotations

SEPARATOR = " › "


def label(primary: str, sub: str | None = None) -> str:
    """'Pets' or 'Pets › Grooming': how a target is named in Settings and in notices."""
    return f"{primary}{SEPARATOR}{sub}" if sub else primary


def split_label(text: str) -> tuple[str, str | None]:
    """label() read back: 'Pets › Grooming' -> ('Pets', 'Grooming'); 'Pets' -> ('Pets', None)."""
    primary, _, sub = text.partition(SEPARATOR)
    return primary, sub or None


def _rows(rows) -> list[dict]:
    return [t for t in rows or [] if isinstance(t, dict)]


def whole(rows) -> dict[str, float]:
    """Targets for whole primary categories, by name."""
    return {t["primary_category"]: float(t["amount"]) for t in _rows(rows) if not t.get("sub_category")}


def subs(rows, primary: str | None = None) -> dict[str, float]:
    """Sub-category targets by sub-category name, for one primary category (or all, by label())."""
    out = {}
    for t in _rows(rows):
        if not t.get("sub_category"):
            continue
        if primary is None:
            out[label(t["primary_category"], t["sub_category"])] = float(t["amount"])
        elif t["primary_category"] == primary:
            out[t["sub_category"]] = float(t["amount"])
    return out
