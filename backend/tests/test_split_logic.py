"""Unit tests for the pure split function — no database, no fixtures."""
from decimal import Decimal

import pytest

from split_logic import settle, split_amount

D = Decimal


@pytest.mark.parametrize("total, shares, expected", [
    # even split
    (D("100.00"), [D("0.5"), D("0.5")], [D("50.00"), D("50.00")]),
    # 60/40 that divides cleanly
    (D("250.00"), [D("0.6"), D("0.4")], [D("150.00"), D("100.00")]),
    # odd cent: the first share rounds, the last absorbs the remainder
    (D("100.01"), [D("0.5"), D("0.5")], [D("50.01"), D("50.00")]),
    # personal expense: one share at 100%
    (D("42.42"), [D("1")], [D("42.42")]),
    # zero amount
    (D("0.00"), [D("0.6"), D("0.4")], [D("0.00"), D("0.00")]),
])
def test_split_amount(total, shares, expected):
    assert split_amount(total, shares) == expected


@pytest.mark.parametrize("total", [D("0.01"), D("10.00"), D("99.99"), D("1234.57"), D("0.03")])
@pytest.mark.parametrize("shares", [
    [D("0.6"), D("0.4")],
    [D("0.3333"), D("0.3333"), D("0.3334")],
    [D("0.6667"), D("0.3333")],
    [D("0.0001"), D("0.9999")],
])
def test_parts_always_sum_to_total(total, shares):
    amounts = split_amount(total, shares)
    assert sum(amounts) == total
    assert len(amounts) == len(shares)
    # every part is a whole number of cents
    assert all(a == a.quantize(D("0.01")) for a in amounts)


def test_remainder_goes_to_last_share():
    # 0.03 at 50/50: the first share rounds 0.015 up to 0.02, the last gets what's left
    assert split_amount(D("0.03"), [D("0.5"), D("0.5")]) == [D("0.02"), D("0.01")]


@pytest.mark.parametrize("shares", [
    [D("0.6"), D("0.6")],
    [D("0.5"), D("0.4")],
    [],
])
def test_shares_not_summing_to_one_raise(shares):
    with pytest.raises(ValueError):
        split_amount(D("100.00"), shares)


def test_tolerates_representation_error_in_shares():
    # three thirds stored at 4dp sum to 0.9999 — within tolerance
    amounts = split_amount(D("10.00"), [D("0.3333")] * 3)
    assert sum(amounts) == D("10.00")


# --- settle ----------------------------------------------------------------

def test_settle_two_people():
    assert settle({1: D("40.00"), 2: D("-40.00")}) == [(2, 1, D("40.00"))]


def test_settle_already_even():
    assert settle({1: D("0.00"), 2: D("0.00")}) == []


def test_settle_no_members():
    assert settle({}) == []


def test_settle_three_people_clears_every_net():
    nets = {1: D("50.00"), 2: D("-30.00"), 3: D("-20.00")}
    transfers = settle(nets)
    assert transfers == [(2, 1, D("30.00")), (3, 1, D("20.00"))]
    for src, dst, amount in transfers:
        nets[src] += amount
        nets[dst] -= amount
    assert all(n == 0 for n in nets.values())


def test_settle_rejects_nets_that_dont_sum_to_zero():
    with pytest.raises(ValueError):
        settle({1: D("40.00"), 2: D("-39.99")})
