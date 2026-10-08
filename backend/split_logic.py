from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple

def split_amount(total: Decimal, shares: List[Decimal]) -> List[Decimal]:
    """
    Splits `total` across `shares` (fractions that must sum to 1), returning
    one amount per share, in the same order.

    Every share except the last is rounded independently to the cent; the
    last absorbs whatever remainder that rounding leaves, so the returned
    amounts always sum exactly to `total` no matter how the individual
    roundings fall.

    No database access and no knowledge of users, expenditures, or settings
    on purpose - it's pure arithmetic, which is what makes it trivial to
    test (see notes/03, Step 5).

    :param total: the amount being split.
    :type total: Decimal
    :param shares: fractions of `total`; must sum to 1 (within a small
        tolerance for representation error).
    :type shares: List[Decimal]
    :raises ValueError: if `shares` don't sum to 1.
    :return: one amount per share, in the same order, summing exactly to `total`.
    :rtype: List[Decimal]
    """
    total_shares = sum(shares)
    if abs(total_shares - 1) > Decimal("0.0001"):
        raise ValueError(f"Shares must sum to 1, got {total_shares}")

    amounts = [
        (total * share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for share in shares[:-1]
    ]

    # The last share gets whatever is left, not its own independently
    # rounded amount – that's what forces the parts to reconcile exactly
    # to `total`.
    remainder = (total - sum(amounts)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amounts.append(remainder)

    return amounts

def settle(nets: Dict[int, Decimal]) -> List[Tuple[int, int, Decimal]]:
    """
    Turns each person's net position into the transfers that clear it.

    A positive net means the household owes that person money; a negative
    one means they owe the household. Returns `(from_id, to_id, amount)`
    transfers, largest debts first, so that after paying them every net is
    zero. With two people that's at most one transfer.

    Like `split_amount`, this is pure arithmetic with no database access.

    :param nets: net position per user id (paid minus borne).
    :type nets: Dict[int, Decimal]
    :raises ValueError: if the nets don't sum to zero - every share of a
        shared expense is borne by someone, so a non-zero sum means an
        allocation didn't reconcile with its expense.
    :return: transfers as (from_user_id, to_user_id, amount).
    :rtype: List[Tuple[int, int, Decimal]]
    """
    total = sum(nets.values(), Decimal("0"))
    if total != 0:
        raise ValueError(f"Net positions must sum to zero, got {total}")

    # Sort by size (ties by id, so the output is deterministic).
    creditors = sorted(([uid, n] for uid, n in nets.items() if n > 0), key=lambda c: (-c[1], c[0]))
    debtors = sorted(([uid, -n] for uid, n in nets.items() if n < 0), key=lambda d: (-d[1], d[0]))

    transfers = []
    ci = di = 0
    while ci < len(creditors) and di < len(debtors):
        amount = min(creditors[ci][1], debtors[di][1])
        transfers.append((debtors[di][0], creditors[ci][0], amount))
        creditors[ci][1] -= amount
        debtors[di][1] -= amount
        if creditors[ci][1] == 0:
            ci += 1
        if debtors[di][1] == 0:
            di += 1

    return transfers
