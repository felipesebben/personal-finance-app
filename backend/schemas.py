from pydantic import BaseModel
from datetime import datetime

class ExpenditureCreate(BaseModel):
    transaction_timestamp: datetime
    price: float
    person_id: int
    category_id: int
    payment_method_id: int

    class Config:
        orm_mode = True