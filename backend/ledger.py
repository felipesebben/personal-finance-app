"""
Database writes shared by the API and the seed script, so seeded data is
built by exactly the code that builds real data.

Nothing here commits: the caller owns the transaction.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

import models
from split_logic import split_amount


class HouseholdNotConfigured(Exception):
    """A shared expense was written before the household split ratio was set."""


class InvalidSplit(Exception):
    """A manual split named someone outside the household."""


class PayerNotInHousehold(Exception):
    """A shared expense was paid by someone outside the household split."""


def add_expenditure(db: Session, payer_id: int, fields: dict, shared: bool,
                    shares: list[tuple[int, Decimal]] | None = None) -> models.FactExpenditure:
    """
    Adds an expenditure paid by `payer_id` and its allocation row(s) to the
    session, without committing.

    `shared` means "split this by the household ratio": one row per member
    with the ratio snapshotted onto it. `shares`, (user_id, share_pct) pairs
    summing to 1, overrides that ratio for this one expense and is recorded
    as split_source "manual". Otherwise the payer bears it alone, in a
    single 100% row.

    :raises HouseholdNotConfigured: if `shared` and the ratio isn't set.
    :raises InvalidSplit: if `shares` names someone outside the household.
    :raises PayerNotInHousehold: if `shared` and the payer has no share,
        which would split their expense between other people entirely.
        Either way the flushed expenditure is still in the session; the
        caller rolls back.
    """
    expenditure = models.FactExpenditure(**fields, user_id=payer_id)
    db.add(expenditure)
    # Flush (not commit) so expenditure_id is assigned without ending the
    # transaction – the split row(s) below still need to land in the same commit.
    db.flush()

    write_splits(db, expenditure, shared, shares)
    return expenditure


def write_splits(db: Session, expenditure: models.FactExpenditure, shared: bool,
                 shares: list[tuple[int, Decimal]] | None = None,
                 keep: list[tuple[int, Decimal, str]] | None = None) -> None:
    """
    Adds the allocation row(s) for `expenditure` (already flushed, so it has
    an id), paid by its user_id, without committing:

    - not `shared`: the payer bears it alone, one 100% "not_shared" row;
    - `shares`: (user_id, share_pct) pairs summing to 1, "manual";
    - `keep`: (user_id, share_pct, split_source) rows to re-apply as they
      were, e.g. an edit that changed only the price keeps the ratio the
      expense was logged with rather than today's;
    - otherwise the household ratio, snapshotted, "household_default".

    Amounts always come from split_amount, so they sum to the price.

    :raises HouseholdNotConfigured, PayerNotInHousehold, InvalidSplit: as
        add_expenditure.
    """
    payer_id = expenditure.user_id
    if not shared:
        db.add(models.FactExpenditureSplit(
            expenditure_id=expenditure.expenditure_id,
            user_id=payer_id,
            share_pct=Decimal("1.0"),
            share_amount=expenditure.price,
            split_source="not_shared",
        ))
        return

    if keep:
        rows = sorted(keep)
    else:
        household = (
            db.query(models.HouseholdSetting)
            .order_by(models.HouseholdSetting.user_id)
            .all()
        )
        if not household:
            raise HouseholdNotConfigured()
        members = {row.user_id for row in household}
        if payer_id not in members:
            raise PayerNotInHousehold()
        if shares:
            outsiders = sorted({uid for uid, _ in shares} - members)
            if outsiders:
                raise InvalidSplit(f"user_id {outsiders} not in the household")
            rows = [(uid, pct, "manual") for uid, pct in sorted(shares)]
        else:
            rows = [(row.user_id, row.share_pct, "household_default") for row in household]
    amounts = split_amount(expenditure.price, [pct for _, pct, _ in rows])

    for (user_id, share_pct, source), share_amount in zip(rows, amounts):
        db.add(models.FactExpenditureSplit(
            expenditure_id=expenditure.expenditure_id,
            user_id=user_id,
            share_pct=share_pct,
            share_amount=share_amount,
            split_source=source,
        ))


def replace_splits(db: Session, expenditure: models.FactExpenditure, shared: bool,
                   shares: list[tuple[int, Decimal]] | None = None,
                   keep: list[tuple[int, Decimal, str]] | None = None) -> None:
    """Deletes the expense's allocation rows and writes new ones (write_splits), without committing."""
    db.query(models.FactExpenditureSplit).filter(
        models.FactExpenditureSplit.expenditure_id == expenditure.expenditure_id
    ).delete(synchronize_session=False)
    db.flush()
    write_splits(db, expenditure, shared, shares, keep)
