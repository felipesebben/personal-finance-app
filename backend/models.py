from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from database import Base

class Expenditure(Base):
    __tablename__ = "fact_expenditures"

    ExpenditureID = Column(Integer, primary_key=True, index=True)
    TransactionTimestamp = Column(DateTime(timezone=True), nullable=False)
    Price = Column(Float, nullable=False) # SQLAlchemy uses Float for DECIMAL

    PersonID = Column(Integer, ForeignKey("dim_person.personid"))
    CategoryID = Column(Integer, ForeignKey("dim_category.categoryid"))
    PaymentMethodID = Column(Integer, ForeignKey("dim_paymentmethod.paymentmethodid"))