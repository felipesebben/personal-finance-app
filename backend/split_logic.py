from decimal import Decimal, ROUND_HALF_UP
from typing import List

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