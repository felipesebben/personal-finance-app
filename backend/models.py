from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

# --- All attributes are now in snake_case ---

class DimPerson(Base):
    __tablename__ = "dim_person"
    person_id = Column(Integer, primary_key=True)
    person_name = Column(String(255), nullable=False, unique=True)

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
    
class Expenditure(Base):
    __tablename__ = "fact_expenditures"

    expenditure_id = Column(Integer, primary_key=True, index=True)
    transaction_timestamp = Column(DateTime(timezone=True), nullable=False)
    price = Column(Float, nullable=False)
    
    # Nature of cost
    nature = Column(String, default="Normal")
    
    # Foreign keys now consistently match the primary key names
    person_id = Column(Integer, ForeignKey("dim_person.person_id"))
    category_id = Column(Integer, ForeignKey("dim_category.category_id"))
    payment_method_id = Column(Integer, ForeignKey("dim_paymentmethod.payment_method_id"))

    # Define the relationships
    person = relationship("DimPerson")
    category = relationship("DimCategory")
    payment_method = relationship("DimPaymentMethod")