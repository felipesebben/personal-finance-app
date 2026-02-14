from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from jose import JWTError , jwt
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import List

from auth import verify_password, create_access_token, get_password_hash, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


from pydantic import BaseModel
import models
import schemas
from database import SessionLocal, engine
from etl.main import run_pipeline

# This line creates the database tables if they don't exist
# based on our models.py definitions.
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Send user to login area if they want to login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Decodes the token, extracts the email, and checks if the user exists.
    
    :param token: Description
    :type token: str
    :param db: Description
    :type db: Session
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        # Decode the token using our secret key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")        
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Check DB:
    user = db.query(models.DimUser).filter(models.DimUser.email == email).first()
    if user is None:
        raise credentials_exception
    
    return user
    

# Create a POST endpoint at the URL /expenditures/.
@app.post("/expenditures/", response_model=schemas.ExpenditureCreate)
def create_expenditure(
    expenditure: schemas.ExpenditureCreate, 
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user)):
    """
    Creates an expenditure linked to the logged-in user.
    """
    # Remove user_id from the request JSON for fraud prevention.
    expenditure_data = expenditure.model_dump(exclude={"user_id"})

    db_expenditure = models.FactExpenditure(
        **expenditure_data,
        user_id=current_user.user_id # Force correct user id
    )

    # Add the new expenditure to the session and commit it to the database
    db.add(db_expenditure)
    db.commit()
    db.refresh(db_expenditure)

    return db_expenditure


@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    db_user = db.query(models.DimUser).filter(models.DimUser.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create the user (We will add hashig here in the following task)
    hashed_pwd = get_password_hash(user.password)
    new_user = models.DimUser(
        email = user.email,
        hashed_password=hashed_pwd,
        full_name=user.full_name
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """
    1. Takes the email/password (via `form_data`).
    2. Checks if they are correct.
    3. Returns a JWT Token.
    """
    # OAuth2 form stores the email in a field called 'username'.
    print(f"Attempting login for: {form_data.username}")
    
    user = db.query(models.DimUser).filter(models.DimUser.email == form_data.username).first()

    # Check 1: Does the user exist? | Check 2: Is password correct?
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # If we get until here, password is correct.
    # Generate the token (passport)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


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


@app.get("/users/", response_model=List[schemas.User])
def get_users(db: Session = Depends(get_db)):
    people = db.query(models.DimUser).all()
    return people

@app.get("/categories/", response_model=List[schemas.Category])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.DimCategory).all()
    return categories

@app.get("/payment_methods/", response_model=List[schemas.PaymentMethod])
def get_payment_methods(db: Session = Depends(get_db)):
    payment_methods = db.query(models.DimPaymentMethod).all()
    return payment_methods

@app.get("/expenditures/", response_model=List[schemas.ExpenditureRead])
def get_expenditures(db: Session = Depends(get_db),
                     current_user: models.DimUser = Depends(get_current_user)):
    """
    Fetch only the expenditures if:
    1. The current user created them
     OR
    2. The expenditure is marked as "Shared" (`is_shared = True`).
    """
    expenditures = (
        db.query(models.FactExpenditure)
        .filter(
            or_(
                models.FactExpenditure.user_id == current_user.user_id,
                models.FactExpenditure.is_shared == True
            )
        )
        .options(
            joinedload(models.FactExpenditure.user),
            joinedload(models.FactExpenditure.category),
            joinedload(models.FactExpenditure.payment_method)
        )
        .all()
    )
    return expenditures

# --- Delete Endpoints ---

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.DimUser).filter(models.DimUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        db.delete(user)
        db.commit()
    except Exception:
        # This happens if you try to delete a user who already has expenditures registered.
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete: This item is used in existing records.")
    
    return {"message": "user deleted successfully"}

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
def delete_expenditure(
    expenditure_id: int, 
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user)):
    """
    Delete an expenditure if:
    1. User owns it 
    OR
    2. It is shared.
    """
    exp = (
        db.query(models.FactExpenditure)
        .filter(models.FactExpenditure.expenditure_id == expenditure_id)
        .filter(
            or_(
                models.FactExpenditure.user_id == current_user.user_id,
                models.FactExpenditure.is_shared == True
            )
        )
        .first()
    )

    if not exp:
        raise HTTPException(status_code=404, detail="Expenditure not found (or you don't have permission)")
    
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