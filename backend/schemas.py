from pydantic import BaseModel
from datetime import datetime


# -- Dimension Schemas --
# Create a base and a full schema for each dimension.

class Person(BaseModel):
    person_id: int
    person_name: str

    class Config:
        from_attributes = True

class Category(BaseModel):
    category_id: int
    primary_category: str
    sub_category: str

    class Config:
        from_attributes = True

class PaymentMethod(BaseModel):
    payment_method_id: int
    method_name: str
    institution: str | None = None # Optional field

    class Config:
        from_attributes = True

# -- Expenditure Schema --     
class ExpenditureCreate(BaseModel):
    transaction_timestamp: datetime
    price: float
    person_id: int
    category_id: int
    payment_method_id: int

    class Config:
        from_attributes = True # Changed from orm_mode