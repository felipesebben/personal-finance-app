from decimal import Decimal

import pytest

from money import (
    entry_preview, format_brl, format_brl_delta, installment_amounts, parse_brl, split_like_backend,
)

D = Decimal


@pytest.mark.parametrize("typed, expected", [
    ("45", D("45.00")),
    ("45,9", D("45.90")),
    ("45,90", D("45.90")),
    ("1.234,56", D("1234.56")),
    ("1234,56", D("1234.56")),
    ("1234.56", D("1234.56")),
    ("12.5", D("12.50")),
    ("1.234", D("1234.00")),
    ("1.234.567,89", D("1234567.89")),
    ("0,5", D("0.50")),
    (",50", D("0.50")),
    ("R$ 12,50", D("12.50")),
    ("r$12,50", D("12.50")),
    ("  1 234,00 ", D("1234.00")),
    ("99999999,99", D("99999999.99")),
])
def test_accepted_formats(typed, expected):
    assert parse_brl(typed) == expected


@pytest.mark.parametrize("typed", [
    "", "   ", "R$", "0", "0,00", "-5", "abc", "1e3", "12,345", "1,234,56",
    "1.23.4", "12.34.56,00", "1.2345", "100000000", "45,9a",
])
def test_rejected_formats(typed):
    with pytest.raises(ValueError):
        parse_brl(typed)


def test_errors_are_readable():
    with pytest.raises(ValueError, match="comma for cents"):
        parse_brl("1.23.4")


@pytest.mark.parametrize("value, expected", [
    (D("1234.5"), "R$ 1.234,50"),
    ("0.1", "R$ 0,10"),
    (1234567.891, "R$ 1.234.567,89"),
    (0, "R$ 0,00"),
    (D("-12"), "-R$ 12,00"),
])
def test_format_brl(value, expected):
    assert format_brl(value) == expected


def test_format_without_symbol():
    assert format_brl("2500", symbol=False) == "2.500,00"


@pytest.mark.parametrize("value", ["0.01", "45.90", "1234.56", "99999999.99"])
def test_round_trip(value):
    assert parse_brl(format_brl(D(value))) == D(value)


# --- Helpers behind the entry form's live preview ---

@pytest.mark.parametrize("value, expected", [
    (D("12"), "+R$ 12,00"),
    ("-3.5", "-R$ 3,50"),
    (0, "R$ 0,00"),
])
def test_format_brl_delta(value, expected):
    assert format_brl_delta(value) == expected


@pytest.mark.parametrize("total, count, first, last", [
    (D("1200.00"), 10, D("120.00"), D("120.00")),
    (D("40.00"), 3, D("13.33"), D("13.34")),
    (D("100.00"), 3, D("33.33"), D("33.34")),
    (D("0.05"), 3, D("0.01"), D("0.03")),   # rounded down, never up
    (D("45.90"), 1, D("45.90"), D("45.90")),
])
def test_installment_amounts_last_takes_remainder(total, count, first, last):
    assert installment_amounts(total, count) == (first, last)
    assert first * (count - 1) + last == total


def test_split_like_backend_last_member_absorbs_remainder():
    # 100.01 at 60/40: 60.006 rounds half up to 60.01, the last gets 40.00.
    assert split_like_backend(D("100.01"), [(1, D("0.6")), (2, D("0.4"))]) == {1: D("60.01"), 2: D("40.00")}
    # Ordered by user_id, not by the order given.
    assert split_like_backend(D("100.01"), [(2, D("0.4")), (1, D("0.6"))]) == {1: D("60.01"), 2: D("40.00")}
    # 0.005 rounds half up for the first share; the last absorbs it.
    assert split_like_backend(D("0.01"), [(1, D("0.5")), (2, D("0.5"))]) == {1: D("0.01"), 2: D("0.00")}


def test_split_like_backend_drops_zero_shares():
    assert split_like_backend(D("50"), [(1, D("0")), (2, D("1"))]) == {2: D("50.00")}


@pytest.mark.parametrize("args, expected", [
    ((D("1200"), 10, [(1, D("0.6")), (2, D("0.4"))], 1), "R$ 1.200,00 · 10x R$ 120,00 · your share 60% = R$ 720,00"),
    ((D("45.90"),), "R$ 45,90"),                                                 # personal, 1x
    ((D("40"), 3), "R$ 40,00 · 3x R$ 13,33 (last R$ 13,34)"),
    ((D("100.01"), 1, [(1, D("0.6")), (2, D("0.4"))], 2), "R$ 100,01 · your share 40% = R$ 40,00"),
    ((D("100"), 1, [(1, D("0.3333")), (2, D("0.6667"))], 1), "R$ 100,00 · your share 33,33% = R$ 33,33"),
    ((D("80"), 1, [(1, D("0")), (2, D("1"))], 1), "R$ 80,00 · your share 0% = R$ 0,00"),
    ((D("80"), 1, [(1, D("0.5")), (2, D("0.5"))], None), "R$ 80,00"),          # who I am is unknown
    ((D("80"), 1, [(1, D("0.5")), (2, D("0.5"))], 9), "R$ 80,00"),             # not in the household
])
def test_entry_preview(args, expected):
    assert entry_preview(*args) == expected
