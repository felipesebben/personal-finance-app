from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from datetime import datetime
from decimal import Decimal
from typing import List

# -- Dimension Schemas --
# Create schemas for dimensions

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class User(BaseModel):
    user_id: int
    email: str
    full_name: str | None = None

    class Config:
        from_attributes = True

class CategoryCreate(BaseModel):
    primary_category: str
    sub_category: str
    # While these were formely optional or defaulted to values in SQL,
    # we'll make them strings for simplicity as of now.
    cost_type: str = "Variable"

class PaymentMethodCreate(BaseModel):
    method_name: str
    institution: str | None = None
    is_credit: bool = False

class Category(BaseModel):
    category_id: int
    primary_category: str
    sub_category: str
    cost_type: str

    class Config:
        from_attributes = True

class PaymentMethod(BaseModel):
    payment_method_id: int
    method_name: str
    institution: str | None = None # Optional field
    is_credit: bool = False

    class Config:
        from_attributes = True

# -- Household Setting Schema --
# The household split ratio: one row per user, snapshotted onto each
# expenditure's allocation rows at write time (see notes/02).
class HouseholdSettingRead(BaseModel):
    user_id: int
    share_pct: Decimal = Field(gt=0, le=1, max_digits=5, decimal_places=4)
    user: User

    class Config:
        from_attributes = True

class HouseholdSettingItem(BaseModel):
    user_id: int
    share_pct: Decimal = Field(gt=0, le=1, max_digits=5, decimal_places=4)

class HouseholdSettingsUpdate(BaseModel):
    """
    Replaces the whole set of household shares in one call, so the table
    can never be left mid-update with shares that don't sum to 1.
    """
    settings: List[HouseholdSettingItem]

    @field_validator("settings")
    @classmethod
    def shares_must_sum_to_one(cls, settings: List[HouseholdSettingItem]):
        total = sum(s.share_pct for s in settings)
        if abs(total - 1) > Decimal("0.0001"):
            raise ValueError(f"share_pct values must sum to 1, got {total}")
        return settings

# -- Expenditure Schema --
class ShareItem(BaseModel):
    """One person's fraction of a single expense, when overriding the household ratio."""
    user_id: int
    share_pct: Decimal = Field(gt=0, le=1, max_digits=5, decimal_places=4)

class ExpenditureCreate(BaseModel):
    transaction_timestamp: datetime
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    user_id: int | None = None
    category_id: int
    payment_method_id: int
    nature: str = "Normal"
    is_shared: bool = True
    # Optional per-expense split ("this one's on her", "70/30 this time"),
    # used instead of the household ratio and stored as split_source "manual".
    # Only valid on a shared expense; omit to use the household ratio.
    shares: List[ShareItem] | None = None

    # Installments: price is the full purchase price, and current_installment
    # is the one billed in the month of transaction_timestamp. The ETL's
    # cashflow datasource spreads the price across the billing months.
    current_installment: int = Field(1, ge=1)
    total_installments: int = Field(1, ge=1)

    class Config:
        from_attributes = True # Changed from orm_mode

    @model_validator(mode="after")
    def installment_within_total(self):
        if self.current_installment > self.total_installments:
            raise ValueError("current_installment cannot be greater than total_installments")
        return self

    @model_validator(mode="after")
    def shares_are_a_valid_split(self):
        if self.shares is None:
            return self
        if not self.is_shared:
            raise ValueError("shares can only be given for a shared expense (is_shared true)")
        if not self.shares:
            raise ValueError("shares must not be empty; omit it to use the household ratio")
        ids = [s.user_id for s in self.shares]
        if len(set(ids)) != len(ids):
            raise ValueError("shares must name each person at most once")
        total = sum(s.share_pct for s in self.shares)
        if abs(total - 1) > Decimal("0.0001"):
            raise ValueError(f"share_pct values must sum to 1, got {total}")
        return self

class ExpenditureRead(BaseModel):
    expenditure_id: int
    transaction_timestamp: datetime
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    nature: str
    # Still published as "is_shared" so clients don't change, but read from
    # FactExpenditure.has_other_share (derived from allocation rows), not
    # from the legacy column.
    is_shared: bool = Field(validation_alias="has_other_share")

    # Nest the other schemas to show full objects
    user: User
    category: Category
    payment_method: PaymentMethod

    class Config:
        from_attributes = True

# -- Balance Schemas --
# Net position over shared expenses: who paid, who bears the cost, and
# the transfer(s) that would settle the difference.
class MemberBalance(BaseModel):
    user_id: int
    full_name: str | None = None
    paid: Decimal   # sum of shared expenses this person paid for
    borne: Decimal  # sum of this person's shares of those expenses
    settled_out: Decimal = Decimal("0.00")  # settlements this person paid to others
    settled_in: Decimal = Decimal("0.00")   # settlements this person received
    net: Decimal    # paid - borne + settled_out - settled_in; positive means they are owed money

class Transfer(BaseModel):
    from_user_id: int
    from_name: str | None = None
    to_user_id: int
    to_name: str | None = None
    amount: Decimal

class BalanceReport(BaseModel):
    month: str | None = None  # "YYYY-MM" in São Paulo time, or None for all time
    members: List[MemberBalance]
    transfers: List[Transfer]

# -- Settlement Schemas --
class SettlementCreate(BaseModel):
    settled_at: datetime
    from_user_id: int
    to_user_id: int
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    # "YYYY-MM": the month whose balance this squares up. Omit for a payment
    # against the running all-time balance.
    month: str | None = Field(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    note: str | None = None

    @model_validator(mode="after")
    def distinct_users(self):
        if self.from_user_id == self.to_user_id:
            raise ValueError("from_user_id and to_user_id must be different people")
        return self

class SettlementRead(BaseModel):
    settlement_id: int
    settled_at: datetime
    month: str | None = None
    from_user_id: int
    from_name: str | None = None
    to_user_id: int
    to_name: str | None = None
    amount: Decimal
    note: str | None = None

# -- Monthly Summary Schemas --
# From the logged-in user's point of view: what they bear (their share of
# shared expenses plus their personal ones), never the other person's
# personal spending.
class AmountBy(BaseModel):
    label: str
    amount: Decimal

class MySpending(BaseModel):
    total: Decimal           # shared_share + personal
    previous_total: Decimal  # same, for the previous month
    shared_share: Decimal    # my share of shared expenses
    personal: Decimal        # my personal expenses

class HouseholdShared(BaseModel):
    total: Decimal           # full price of shared expenses, whoever paid
    previous_total: Decimal

class MonthlySummary(BaseModel):
    month: str               # "YYYY-MM", São Paulo calendar month
    previous_month: str
    me: MySpending
    household_shared: HouseholdShared
    by_category: List[AmountBy]   # my spending per primary category, largest first
    by_cost_type: List[AmountBy]  # my spending per cost type, largest first

class Token(BaseModel):
    """
    Schema for the JWT Token response.
    """
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    Schema for the data embedded inside the Token.
    """
    email: str | None = None