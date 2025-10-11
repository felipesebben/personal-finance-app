from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import SessionLocal, engine

# This line creates the database tables if they don't exist
# based on our models.py definitions.
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency to get a DB session for each request
def get_db():
    """
    - For each incoming request, opens a new database session and then makes sure to close it when the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create a POST endpoint at the URL /expenditures/.
@app.post("/expenditures/", response_model=schemas.ExpenditureCreate)
def create_expenditure(expenditure: schemas.ExpenditureCreate, db: Session = Depends(get_db)): # Runs the get_db function and pass the resulting database session to our endpoint.
    # Create a SQLAlchemy model instance from the Pydantic schema data
    db_expenditure = models.Expenditure(**expenditure.model_dump())

    # Add the new expenditure to the session and commit it to the database
    db.add(db_expenditure)
    db.commit()
    db.refresh(db_expenditure)

    return db_expenditure

@app.get("/people/", response_model=List[schemas.Person])
def get_people(db: Session = Depends(get_db)):
    people = db.query(models.DimPerson).all()
    return people

@app.get("/categories/", response_model=List[schemas.Category])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.DimCategory).all()
    return categories

@app.get("/payment_methods/", response_model=List[schemas.PaymentMethod])
def get_payment_methods(db: Session = Depends(get_db)):
    payment_methods = db.query(models.DimPaymentMethod).all()
    return payment_methods
