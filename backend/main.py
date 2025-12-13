from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
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

@app.post("/people/", response_model=schemas.Person)
def create_person(person: schemas.PersonCreate, db: Session = Depends(get_db)):
    db_person = models.DimPerson(**person.model_dump())
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return db_person

@app.post("/categories/", response_model=schemas.Category)
def create_category(category: schemas.CategoryCreate, db: Session=Depends(get_db)):
    db_category = models.DimCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.post("/payment_methods/", response_model=schemas.PaymentMethod)
def create_payment_method(method: schemas.PaymentMethodCreate, db: Session=Depends(get_db)):
    db_method = models.DimPaymentMethod(**method.model_dump())
    db.add(db_method)
    db.commit()
    db.refresh(db_method)
    return db_method


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

# New: Get All expenditures endpoint
@app.get("/expenditures/", response_model=List[schemas.ExpenditureRead])
def get_expenditures(db: Session = Depends(get_db)):
    """
    Fetch all expenditures with their related dimension data.
    """
    expenditures = (
        db.query(models.Expenditure)
        .options(
            joinedload(models.Expenditure.person),
            joinedload(models.Expenditure.category),
            joinedload(models.Expenditure.payment_method)
        )
        .all()
    )
    return expenditures