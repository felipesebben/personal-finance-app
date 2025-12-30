from pydantic import BaseModel
from datetime import datetime


# -- Dimension Schemas --
# Create schemas for dimensions

class PersonCreate(BaseModel):
    person_name: str

class CategoryCreate(BaseModel):
    primary_category: str
    sub_category: str
    # While these were formely optional or defaulted to values in SQL,
    # we'll make them strings for simplicity as of now.
    cost_type: str = "Variable"

class PaymentMethodCreate(BaseModel):
    method_name: str
    institution: str | None = None

    
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
    nature: str = "Normal"
    is_shared: bool = True

    class Config:
        from_attributes = True # Changed from orm_mode

class ExpenditureRead(BaseModel):
    expenditure_id: int
    transaction_timestamp: datetime
    price: float
    nature: str
    is_shared: bool

    # Nest the other schemas to show full objects
    person: Person
    category: Category
    payment_method: PaymentMethod

    class Config:
        from_attributes = True