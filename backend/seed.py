"""
Seeds several months of realistic household history for analytics work:
shared and personal expenses with their allocation rows, plus a settlement
squaring up each finished month.

Run on demand, never at startup, from backend/ (or inside the container):

    python seed.py                  # 6 months ending this month
    python seed.py --months 12 --random-seed 7

Expenses are written through ledger.add_expenditure, the same code
POST /expenditures/ uses, so seeded split rows follow the real rules. It
uses the household already configured on Manage Settings (it never creates
users) and refuses to write into months that already hold expenses unless
--append is given, so running it twice doesn't silently double the data.
"""
import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from ledger import add_expenditure
from split_logic import settle

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class SeedRefused(Exception):
    """The database isn't in a state the seed should write into."""


@dataclass(frozen=True)
class Spend:
    primary: str
    sub: str
    cost_type: str
    low: float          # price range, BRL
    high: float
    per_month: int      # how many per month
    shared_odds: float  # chance each one is split by the household ratio


# Fixed costs land on the 5th or 10th; everything else on a random day.
CATALOGUE = [
    Spend("Housing", "Condo Fees", "Fixed", 400, 900, 1, 1.0),
    Spend("Housing", "Electricity", "Fixed", 110, 400, 1, 1.0),
    Spend("Housing", "Internet", "Fixed", 100, 150, 1, 1.0),
    Spend("Housing", "House Gas", "Variable", 50, 100, 1, 1.0),
    Spend("Food", "Groceries", "Variable", 50, 800, 6, 0.9),
    Spend("Food", "Eating Out", "Variable", 30, 600, 4, 0.5),
    Spend("Transport", "Fuel", "Variable", 100, 280, 3, 0.3),
    Spend("Transport", "Rideshare", "Variable", 10, 100, 3, 0.1),
    Spend("Leisure", "Streaming", "Fixed", 40, 60, 1, 1.0),
    Spend("Health", "Pharmacy", "Variable", 20, 250, 1, 0.5),
    Spend("Personal", "Clothing", "Variable", 80, 500, 1, 0.0),
]

PAYMENT_METHODS = [("Pix", None, False), ("Debit Card", None, False), ("Credit Card", None, True)]


def months_ending(today: date, count: int) -> list[date]:
    """First day of each of the `count` months ending with `today`'s, oldest first."""
    months = []
    y, m = today.year, today.month
    for _ in range(count):
        months.append(date(y, m, 1))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return months[::-1]


def next_month(month: date) -> date:
    return date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)


def get_or_create_category(db: Session, spend: Spend) -> int:
    row = db.query(models.DimCategory).filter_by(primary_category=spend.primary, sub_category=spend.sub).first()
    if row is None:
        row = models.DimCategory(primary_category=spend.primary, sub_category=spend.sub, cost_type=spend.cost_type)
        db.add(row)
        db.flush()
    return row.category_id


def get_or_create_payment_method(db: Session, name: str, institution: str | None, is_credit: bool) -> int:
    # The unique constraint treats NULL institutions as distinct, so match on IS NULL explicitly.
    row = db.query(models.DimPaymentMethod).filter(
        models.DimPaymentMethod.method_name == name,
        models.DimPaymentMethod.institution.is_(None) if institution is None
        else models.DimPaymentMethod.institution == institution,
    ).first()
    if row is None:
        row = models.DimPaymentMethod(method_name=name, institution=institution, is_credit=is_credit)
        db.add(row)
        db.flush()
    return row.payment_method_id


def seed(db: Session, months: int = 6, rng: random.Random | None = None,
         today: date | None = None, append: bool = False) -> dict:
    """
    Writes `months` months of history ending with `today`'s month, and
    commits once at the end. Returns counts of what was written.

    :raises SeedRefused: if no household ratio is set, or the months already
        hold expenses and `append` is False.
    """
    rng = rng or random.Random()
    now = datetime.now(SAO_PAULO)
    today = today or now.date()
    if months < 1:
        raise SeedRefused("--months must be at least 1")

    household = [row.user_id for row in db.query(models.HouseholdSetting).order_by(models.HouseholdSetting.user_id)]
    if not household:
        raise SeedRefused("Household split ratio is not configured. Set it on the Manage Settings page first.")

    window = months_ending(today, months)
    window_start = datetime.combine(window[0], time(), SAO_PAULO)
    existing = db.query(func.count(models.FactExpenditure.expenditure_id)).filter(
        models.FactExpenditure.transaction_timestamp >= window_start
    ).scalar()
    if existing and not append:
        raise SeedRefused(
            f"{existing} expenses already exist since {window[0]:%Y-%m}. "
            "Pass --append to add seeded ones alongside them."
        )

    categories = {spend: get_or_create_category(db, spend) for spend in CATALOGUE}
    methods = [get_or_create_payment_method(db, *pm) for pm in PAYMENT_METHODS]
    # Use the time of day too, so nothing seeded today lands after "now".
    latest = datetime.combine(today, now.timetz()) if today == now.date() else datetime.combine(today, time(23, 59), SAO_PAULO)

    counts = {"expenditures": 0, "shared": 0, "personal": 0, "settlements": 0}
    for month in window:
        last_day = (next_month(month) - month).days
        nets = {uid: Decimal("0") for uid in household}

        for spend in CATALOGUE:
            for _ in range(spend.per_month):
                day = rng.choice([5, 10]) if spend.cost_type == "Fixed" else rng.randint(1, last_day)
                when = datetime.combine(
                    date(month.year, month.month, day),
                    time(rng.randint(8, 21), rng.randint(0, 59)),
                    SAO_PAULO,
                )
                if when > latest:
                    continue  # this month isn't over yet
                payer = rng.choice(household)
                shared = rng.random() < spend.shared_odds
                price = Decimal(str(round(rng.uniform(spend.low, spend.high), 2)))
                exp = add_expenditure(db, payer, {
                    "transaction_timestamp": when,
                    "price": price,
                    "category_id": categories[spend],
                    "payment_method_id": rng.choice(methods),
                    "nature": "Recurring" if spend.cost_type == "Fixed" else "Normal",
                }, shared=shared)

                counts["expenditures"] += 1
                counts["shared" if shared else "personal"] += 1
                if shared:
                    db.flush()
                    nets[payer] += price
                    for row in db.query(models.FactExpenditureSplit).filter_by(expenditure_id=exp.expenditure_id):
                        nets[row.user_id] -= row.share_amount

        # Square up each finished month early in the next one, as the household does.
        settled_at = datetime.combine(next_month(month).replace(day=5), time(19, 0), SAO_PAULO)
        if settled_at > latest:
            continue
        for src, dst, amount in settle(nets):
            db.add(models.FactSettlement(
                settled_at=settled_at, period_month=month,
                from_user_id=src, to_user_id=dst, amount=amount,
                note=f"Settle {month:%Y-%m}", recorded_by_user_id=src,
            ))
            counts["settlements"] += 1

    db.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--months", type=int, default=6, help="months of history, ending this month (default 6)")
    parser.add_argument("--random-seed", type=int, default=None, help="make the output reproducible")
    parser.add_argument("--append", action="store_true", help="write even if the months already hold expenses")
    args = parser.parse_args()

    from database import SessionLocal
    with SessionLocal() as db:
        try:
            counts = seed(db, months=args.months, rng=random.Random(args.random_seed), append=args.append)
        except SeedRefused as e:
            raise SystemExit(f"Not seeding: {e}")
    print(
        f"Seeded {counts['expenditures']} expenses ({counts['shared']} shared, "
        f"{counts['personal']} personal) and {counts['settlements']} settlements "
        f"over {args.months} months."
    )


if __name__ == "__main__":
    main()
