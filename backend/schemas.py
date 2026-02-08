from pydantic import BaseModel, EmailStr
from datetime import datetime


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

    class Config:
        from_attributes = True

# -- Expenditure Schema --     
class ExpenditureCreate(BaseModel):
    transaction_timestamp: datetime
    price: float
    user_id: int | None = None
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
    user: User
    category: Category
    payment_method: PaymentMethod

    class Config:
        from_attributes = True

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