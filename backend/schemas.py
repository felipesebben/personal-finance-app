from pydantic import BaseModel, EmailStr, Field, field_validator
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
class ExpenditureCreate(BaseModel):
    transaction_timestamp: datetime
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    user_id: int | None = None
    category_id: int
    payment_method_id: int
    nature: str = "Normal"
    is_shared: bool = True

    # Tell API to accept these (with defaults)
    current_installment: int = 1
    total_installments: int = 1

    class Config:
        from_attributes = True # Changed from orm_mode

class ExpenditureRead(BaseModel):
    expenditure_id: int
    transaction_timestamp: datetime
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    nature: str
    is_shared: bool

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
    net: Decimal    # paid - borne; positive means they are owed money

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