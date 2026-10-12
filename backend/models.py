from sqlalchemy import Column, Boolean, CheckConstraint, Date, Integer, Numeric, DateTime, ForeignKey, String, UniqueConstraint, exists, func
from sqlalchemy.orm import aliased, column_property, relationship
from database import Base


class DimUser(Base):
    __tablename__ = "dim_user"

    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Store the hash, not the password itself
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)

    # Relationship - one user has many expenditures
    expenditures = relationship("FactExpenditure", back_populates="user")

class DimPaymentMethod(Base):
    __tablename__ = "dim_payment_method"
    payment_method_id = Column(Integer, primary_key=True)
    method_name = Column(String(255), nullable=False)
    institution = Column(String(255), nullable=True)
    is_credit = Column(Boolean, default=False)
    # A household account both people fund in advance: what it pays for is
    # already settled between them, so it never makes anyone owe anyone.
    is_joint = Column(Boolean, nullable=False, server_default="false", default=False)

    __table_args__ = (
        UniqueConstraint("method_name", "institution", name="uq_payment_method"),
    )

class HouseholdSetting(Base):
    __tablename__ = "household_setting"
    user_id = Column(Integer, ForeignKey("dim_user.user_id"), primary_key=True)
    share_pct = Column(Numeric(5, 4), nullable=False)

    user = relationship("DimUser")

class DimCategory(Base):
    __tablename__ = "dim_category"
    category_id = Column(Integer, primary_key=True, index=True)
    primary_category = Column(String(255), nullable=False)
    sub_category = Column(String(255), nullable=False)
    cost_type = Column(String(50), nullable=False)
    # Expenses in this category are for the pets, so Add expense asks which
    # one (see FactExpenditure.pet_id).
    for_pets = Column(Boolean, nullable=False, server_default="false", default=False)

    __table_args__ = (
        UniqueConstraint('primary_category', 'sub_category',name="uq_category"),
    )


class DimPet(Base):
    __tablename__ = "dim_pet"
    pet_id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)


class FactExpenditure(Base):
    __tablename__ = "fact_expenditures"

    expenditure_id = Column(Integer, primary_key=True, index=True)
    transaction_timestamp = Column(DateTime(timezone=True), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    nature = Column(String, default="Normal")
    # Whether it's shared isn't stored: see has_other_share, defined below
    # FactExpenditureSplit. (The old is_shared column was dropped in
    # migration "drop is_shared from fact_expenditures".)

    # Installment tracking
    current_installment = Column(Integer, default=1)
    total_installments = Column(Integer, default=1)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("dim_user.user_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("dim_category.category_id"))
    payment_method_id = Column(Integer, ForeignKey("dim_payment_method.payment_method_id"))
    # Only for a for_pets category: the pet it was for, or NULL for all of
    # them ("Both"). Always NULL for any other category.
    pet_id = Column(Integer, ForeignKey("dim_pet.pet_id", name="fk_fact_expenditures_pet_id"), nullable=True)

    # Define the relationships
    user = relationship("DimUser", back_populates="expenditures")
    category = relationship("DimCategory")
    payment_method = relationship("DimPaymentMethod")
    pet = relationship("DimPet")

class FactExpenditureSplit(Base):
    __tablename__ = "fact_expenditure_split"

    expenditure_id = Column(Integer, ForeignKey("fact_expenditures.expenditure_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("dim_user.user_id"), primary_key=True)
    share_pct = Column(Numeric(5, 4), nullable=False)
    share_amount = Column(Numeric(10, 2), nullable=False)

    # split_source = "household_default" (used the current household ratio)
    # "manual" (this expense's split was deliberately overridden)
    # "not_shared" (personal expense, not split – one row at 100%)
    split_source = Column(String, nullable=False)
    expenditure = relationship("FactExpenditure")
    user = relationship("DimUser")



# Whether an expense is shared is derived from its allocation rows: it's
# shared when someone other than the payer bears part of it. Defined here, after FactExpenditureSplit exists, so every
# query and response uses the same definition (FactExpenditure.has_other_share).
_other_share = aliased(FactExpenditureSplit)
FactExpenditure.has_other_share = column_property(
    exists().where(
        _other_share.expenditure_id == FactExpenditure.expenditure_id,
        _other_share.user_id != FactExpenditure.user_id,
    )
)

class FactSettlement(Base):
    """
    Money moved between household members to square up shared expenses.
    Subtracts out of the /balances/ net position: when Bob pays Alice 40,
    Bob's net rises by 40 and Alice's falls by 40.
    """
    __tablename__ = "fact_settlement"

    settlement_id = Column(Integer, primary_key=True, index=True)
    # When the money actually moved.
    settled_at = Column(DateTime(timezone=True), nullable=False)
    # Which month's balance this squares up (first day of that month), or
    # NULL for a payment against the running all-time balance. Kept apart
    # from settled_at because October is usually settled in early November.
    period_month = Column(Date, nullable=True)
    from_user_id = Column(Integer, ForeignKey("dim_user.user_id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("dim_user.user_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    note = Column(String, nullable=True)
    recorded_by_user_id = Column(Integer, ForeignKey("dim_user.user_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_settlement_amount_positive"),
        CheckConstraint("from_user_id <> to_user_id", name="ck_settlement_distinct_users"),
    )

    from_user = relationship("DimUser", foreign_keys=[from_user_id])
    to_user = relationship("DimUser", foreign_keys=[to_user_id])


class FactJointEntry(Base):
    """
    Money going into a joint account, so the app knows what's left in it.
    A "deposit" adds to the pot; a "balance" says what the bank showed at
    that moment (the starting balance, or a correction when unlogged
    spending has made the app drift). What's left is the latest balance
    plus deposits since, minus what the account paid since. Who deposited
    isn't recorded: the pot is the household's, and deposits never affect
    who owes whom.
    """
    __tablename__ = "fact_joint_entry"

    joint_entry_id = Column(Integer, primary_key=True)
    payment_method_id = Column(Integer, ForeignKey("dim_payment_method.payment_method_id"), nullable=False)
    kind = Column(String(20), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    entry_at = Column(DateTime(timezone=True), nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("kind IN ('deposit', 'balance')", name="ck_joint_entry_kind"),
        CheckConstraint("amount >= 0", name="ck_joint_entry_amount_not_negative"),
    )

    payment_method = relationship("DimPaymentMethod")


class PasswordResetToken(Base):
    """
    A one-time password-reset link. Only the SHA-256 of the token is stored,
    so a leaked database (or pgAdmin screen) can't be used to reset anyone's
    password; the raw token exists only in the email that was sent.
    """
    __tablename__ = "password_reset_token"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("dim_user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # Set when the token is redeemed, or superseded by a newer request.
    used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )

    user = relationship("DimUser")
