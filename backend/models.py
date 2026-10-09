from sqlalchemy import Column, Boolean, CheckConstraint, Date, Integer, Numeric, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
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
    
    __table_args__ = (
        UniqueConstraint('primary_category', 'sub_category',name="uq_category"),
    )
    
class FactExpenditure(Base):
    __tablename__ = "fact_expenditures"

    expenditure_id = Column(Integer, primary_key=True, index=True)
    transaction_timestamp = Column(DateTime(timezone=True), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    nature = Column(String, default="Normal")
    is_shared = Column(Boolean, default=True)

    # Installment tracking
    current_installment = Column(Integer, default=1)
    total_installments = Column(Integer, default=1)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("dim_user.user_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("dim_category.category_id"))
    payment_method_id = Column(Integer, ForeignKey("dim_payment_method.payment_method_id"))

    # Define the relationships
    user = relationship("DimUser", back_populates="expenditures")
    category = relationship("DimCategory")
    payment_method = relationship("DimPaymentMethod")

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
