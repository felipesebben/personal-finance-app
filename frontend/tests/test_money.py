from decimal import Decimal

import pytest

from money import format_brl, parse_brl

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
