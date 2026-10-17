from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal

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
    for_pets: bool = False

class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class Pet(BaseModel):
    pet_id: int
    name: str
    expense_count: int = 0

    class Config:
        from_attributes = True

class PaymentMethodCreate(BaseModel):
    method_name: str
    institution: str | None = None
    is_credit: bool = False
    is_joint: bool = False

class CategoryUpdate(BaseModel):
    """A partial edit: only the fields sent are changed."""
    primary_category: str | None = Field(default=None, min_length=1)
    sub_category: str | None = Field(default=None, min_length=1)
    cost_type: Literal["Fixed", "Variable"] | None = None
    for_pets: bool | None = None

class PaymentMethodUpdate(BaseModel):
    """A partial edit; send institution null to clear it."""
    method_name: str | None = Field(default=None, min_length=1)
    institution: str | None = None
    is_credit: bool | None = None
    is_joint: bool | None = None

class Category(BaseModel):
    category_id: int
    primary_category: str
    sub_category: str
    cost_type: str
    # Expenses in it are for the pets, so Add expense asks which one.
    for_pets: bool = False
    # How many expenses use it; one in use can't be deleted.
    expense_count: int = 0

    class Config:
        from_attributes = True

class PaymentMethod(BaseModel):
    payment_method_id: int
    method_name: str
    institution: str | None = None # Optional field
    is_credit: bool = False
    # Paid from a household account both fund in advance: nobody owes anybody.
    is_joint: bool = False
    expense_count: int = 0

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

    # Only with a for_pets category: the pet it was for. Omitted (None) on a
    # pet category means all of them ("Both").
    pet_id: int | None = None

    # "It's on me": still shared and split, but the payer treated, so it
    # never makes anyone owe them. Only for a shared expense.
    is_treat: bool = False

    # The request is refused (409) when it looks like an expense already
    # logged; send true to save it anyway.
    allow_duplicate: bool = False

    class Config:
        from_attributes = True # Changed from orm_mode

    @model_validator(mode="after")
    def treat_is_shared(self):
        if self.is_treat and not self.is_shared:
            raise ValueError("Only a shared expense can be on you (is_treat needs is_shared true)")
        return self

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
    # The logged-in user's part of this expense (their share_amount; 0 if they
    # hold no share, e.g. one they paid but put entirely on their partner).
    my_share: Decimal = Decimal("0.00")
    # The payer treated: nobody owes them for it.
    is_treat: bool = False

    # Nest the other schemas to show full objects
    user: User
    category: Category
    payment_method: PaymentMethod
    # The pet it was for; None on a pet category means all of them.
    pet: Pet | None = None

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

# -- Joint account Schemas --
class JointEntryCreate(BaseModel):
    payment_method_id: int
    # "deposit": money put in. "balance": what the bank shows right now.
    kind: Literal["deposit", "balance"]
    amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    entry_at: datetime
    note: str | None = None

    @model_validator(mode="after")
    def deposit_is_positive(self):
        if self.kind == "deposit" and self.amount == 0:
            raise ValueError("A deposit must be more than zero")
        return self

class JointEntryRead(BaseModel):
    joint_entry_id: int
    payment_method_id: int
    kind: str
    amount: Decimal
    entry_at: datetime
    note: str | None = None

    class Config:
        from_attributes = True

class JointDay(BaseModel):
    day: int
    this_month: Decimal | None = None  # None after today
    usual: Decimal | None = None       # None without a full month of history

class JointStatus(BaseModel):
    """One joint account, now: what's left, and this month's pace."""
    payment_method_id: int
    label: str
    # None until a balance or deposit has been recorded.
    balance: Decimal | None = None
    # The balance check it counts from, if any (else the first deposit).
    counted_from: datetime | None = None
    deposits_since: Decimal
    spent_since: Decimal
    month: str               # "YYYY-MM", the current São Paulo month
    as_of_day: int
    days_in_month: int
    spent_to_day: Decimal
    usual_to_day: Decimal | None = None
    usual_month_total: Decimal | None = None
    history_months: int      # full months behind "usual", 0 to 3
    runs_out_on: date | None = None
    days: List[JointDay]

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

# -- Shared-expense Analytics Schemas --
# Only expenses that are shared (someone other than the payer holds a split
# row) AND that the logged-in user holds a share of. Two lenses on the same
# expenses: "household" is the full price, "mine" is the user's share_amount.
class SharedAnalyticsRow(BaseModel):
    month: str               # "YYYY-MM", São Paulo calendar month
    primary_category: str
    sub_category: str
    cost_type: str
    nature: str              # Normal / Recurring / Annual / Extraordinary
    household: Decimal       # sum of full prices
    mine: Decimal            # sum of my share_amount
    count: int               # number of shared expenses
    household_to_day: Decimal  # same, only days 1..as_of_day of the month
    mine_to_day: Decimal

class SharedAnalytics(BaseModel):
    month: str               # the selected (last) month of the window
    months: List[str]        # the whole window, oldest first, including empty months
    is_partial: bool         # true when `month` is the current São Paulo month
    as_of_day: int           # today's São Paulo day if partial, else the month's length
    rows: List[SharedAnalyticsRow]  # only non-empty month/category combinations

class DailyRow(BaseModel):
    date: date               # a São Paulo calendar day
    primary_category: str
    sub_category: str
    cost_type: str           # Fixed / Variable ("Unknown" without a category)
    nature: str              # Normal / Recurring / Annual / Extraordinary
    household: Decimal       # sum of full prices
    mine: Decimal            # sum of my share
    count: int               # expenses

class DailyAnalytics(BaseModel):
    month: str               # the selected (last) month of the window, "YYYY-MM"
    months: List[str]        # the whole window, oldest first
    is_partial: bool         # true when `month` is the current São Paulo month
    as_of_day: int           # today's São Paulo day if partial, else the month's length
    today: date              # today in São Paulo
    rows: List[DailyRow]     # day x category x cost type x nature, only where something was spent

class SharedExpense(BaseModel):
    expenditure_id: int
    transaction_timestamp: datetime
    primary_category: str
    sub_category: str
    cost_type: str
    payment_method: str | None = None
    institution: str | None = None
    paid_by: str | None = None
    price: Decimal           # household lens: the full price
    mine: Decimal            # my share_amount
    share_pct: Decimal       # my share_pct
    current_installment: int | None = None
    total_installments: int | None = None
    nature: str | None = None

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

# -- Password reset --

PASSWORD_MIN_LENGTH = 8


class PasswordResetRequest(BaseModel):
    # A plain string rather than EmailStr: the response must not differ
    # between addresses, and an unknown address simply matches no account.
    email: str = Field(max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH)

    @field_validator("new_password")
    @classmethod
    def fits_bcrypt(cls, v: str) -> str:
        # bcrypt only reads the first 72 bytes and the library rejects more.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("must be at most 72 bytes")
        return v


class Message(BaseModel):
    detail: str
