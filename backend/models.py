from sqlalchemy import Column, Boolean, Integer, Float, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class DimUser(Base):
    __tablename__ = "dim_users"

    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Store the hash, not the password itself
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)

    # Relationship - one user has many expenditures
    expenditures = relationship("FactExpenditure", back_populates="user")

class DimPaymentMethod(Base):
    __tablename__ = "dim_paymentmethod"
    payment_method_id = Column(Integer, primary_key=True)
    method_name = Column(String(255), nullable=False)
    institution = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("method_name", "institution", name="uq_payment_method"),
    )

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
    price = Column(Float, nullable=False)
    nature = Column(String, default="Normal")
    is_shared = Column(Boolean, default=True)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("dim_users.user_id"), nullable=False)
    
    category_id = Column(Integer, ForeignKey("dim_category.category_id"))
    payment_method_id = Column(Integer, ForeignKey("dim_paymentmethod.payment_method_id"))

    # Define the relationships
    user = relationship("DimUser", back_populates="expenditures")
    category = relationship("DimCategory")
    payment_method = relationship("DimPaymentMethod")