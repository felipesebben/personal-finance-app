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


def add_expenditure(db: Session, payer_id: int, fields: dict, shared: bool) -> models.FactExpenditure:
    """
    Adds an expenditure paid by `payer_id` and its allocation row(s) to the
    session, without committing.

    `shared` means "split this by the household ratio": one row per member
    with the ratio snapshotted onto it. Otherwise the payer bears it alone,
    in a single 100% row.

    :raises HouseholdNotConfigured: if `shared` and the ratio isn't set. The
        flushed expenditure is still in the session; the caller rolls back.
    """
    expenditure = models.FactExpenditure(**fields, user_id=payer_id)
    db.add(expenditure)
    # Flush (not commit) so expenditure_id is assigned without ending the
    # transaction – the split row(s) below still need to land in the same commit.
    db.flush()

    if shared:
        household = (
            db.query(models.HouseholdSetting)
            .order_by(models.HouseholdSetting.user_id)
            .all()
        )
        if not household:
            raise HouseholdNotConfigured()
        shares = [row.share_pct for row in household]
        amounts = split_amount(expenditure.price, shares)

        for row, share_amount in zip(household, amounts):
            db.add(models.FactExpenditureSplit(
                expenditure_id=expenditure.expenditure_id,
                user_id=row.user_id,
                share_pct=row.share_pct,
                share_amount=share_amount,
                split_source="household_default",
            ))
    else:
        db.add(models.FactExpenditureSplit(
            expenditure_id=expenditure.expenditure_id,
            user_id=payer_id,
            share_pct=Decimal("1.0"),
            share_amount=expenditure.price,
            split_source="not_shared",
        ))

    return expenditure
