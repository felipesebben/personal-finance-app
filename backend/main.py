from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from pydantic import BaseModel
import models
import schemas
from database import SessionLocal, engine
from etl.main import run_pipeline

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
    db_expenditure = models.FactExpenditure(**expenditure.model_dump())

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
        db.query(models.FactExpenditure)
        .options(
            joinedload(models.FactExpenditure.person),
            joinedload(models.FactExpenditure.category),
            joinedload(models.FactExpenditure.payment_method)
        )
        .all()
    )
    return expenditures

# New: DELETE Endpoints

@app.delete("/people/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    person = db.query(models.DimPerson).filter(models.DimPerson.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    try:
        db.delete(person)
        db.commit()
    except Exception:
        # This happens if you try to delete a person who already has expenditures registered.
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete: This item is used in existing records.")
    
    return {"message": "Person deleted successfully"}

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(models.DimCategory).filter(models.DimCategory.category_id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    try:
        db.delete(category)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete: This category is used in existign records.")
    
    return {"message": "Category deleted successfully"}

@app.delete("/payment_methods/{payment_method_id}")
def delete_payment_method(payment_method_id: int, db: Session = Depends(get_db)):
    method = db.query(models.DimPaymentMethod).filter(models.DimPaymentMethod.payment_method_id == payment_method_id).first()
    if not method:
        raise HTTPException(status_code=404, detail="Payment Method not found")
    try:
        db.delete(method)
        db.commit()
    except Exception: 
        db.rollback()   
        raise HTTPException(status_code=400, detail="Cannot delete: this payment method is used in existing records")
    
    return {"message": "Payment Method deleted successfully"}

@app.delete("/expenditures/{expenditure_id}")
def delete_expenditure(expenditure_id: int, db: Session = Depends(get_db)):
    exp = db.query(models.FactExpenditure).filter(models.FactExpenditure.expenditure_id == expenditure_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expenditure not found")
    
    db.delete(exp)
    db.commit()
    return {"message": "Deleted successfully"}

@app.post("/refresh")
def refresh_data():
    """
    Triggers the ETL to update the database and Tableau.
    """
    try:
        print("API received request: Starting ETL process...")

        # Calls the function to run pipeline
        run_pipeline()

        return {"status": "success", "message": "Data refreshed successfully!"}
    
    except Exception as e:
        print(f"ETL Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))