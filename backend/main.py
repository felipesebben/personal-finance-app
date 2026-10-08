from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from jose import JWTError , jwt
from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import exists, or_, func, select
from sqlalchemy.exc import IntegrityError
from typing import List
from decimal import Decimal
from split_logic import split_amount, settle

from auth import verify_password, create_access_token, get_password_hash, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


from pydantic import BaseModel
import models
import schemas
from database import SessionLocal
from etl.main import run_pipeline

app = FastAPI()

# Reporting months are calendar months in the household's timezone.
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

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
    Creates an expenditure linked to the logged-in user, along with its
    allocation row(s) in the same transaction.
    """
    # Remove user_id from the request JSON for fraud prevention.
    expenditure_data = expenditure.model_dump(exclude={"user_id"})

    db_expenditure = models.FactExpenditure(
        **expenditure_data,
        user_id=current_user.user_id # Force correct user id
    )

    db.add(db_expenditure)
    # Flush (not commit) so expenditure_id is assigned without ending
    # the transaction – the split row(s) below still need to land in
    # the same commit.
    db.flush()

    if db_expenditure.is_shared:
        household = (
            db.query(models.HouseholdSetting)
            .order_by(models.HouseholdSetting.user_id)
            .all()
        )
        if not household:
            # Nothing committed yet, so the flushed expenditure is rolled back too.
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Household split ratio is not configured. Set it on the Manage Settings page first.",
            )
        user_ids = [row.user_id for row in household]
        shares = [row.share_pct for row in household]
        amounts = split_amount(db_expenditure.price, shares)

        for user_id, share_pct, share_amount in zip(user_ids, shares, amounts):
            db.add(models.FactExpenditureSplit(
                expenditure_id=db_expenditure.expenditure_id,
                user_id=user_id,
                share_pct=share_pct,
                share_amount=share_amount,
                split_source="household_default",
            ))
    else:
        db.add(models.FactExpenditureSplit(
            expenditure_id=db_expenditure.expenditure_id,
            user_id=current_user.user_id,
            share_pct=Decimal("1.0"),
            share_amount=db_expenditure.price,
            split_source="not_shared"
        ))

    # One commit, covering the expenditure and its allocation row(s) together.
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
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


@app.post("/categories/", response_model=schemas.Category, dependencies=[Depends(get_current_user)])
def create_category(category: schemas.CategoryCreate, db: Session=Depends(get_db)):
    db_category = models.DimCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.post("/payment_methods/", response_model=schemas.PaymentMethod, dependencies=[Depends(get_current_user)])
def create_payment_method(method: schemas.PaymentMethodCreate, db: Session=Depends(get_db)):
    db_method = models.DimPaymentMethod(**method.model_dump())
    db.add(db_method)
    db.commit()
    db.refresh(db_method)
    return db_method


@app.get("/users/", response_model=List[schemas.User], dependencies=[Depends(get_current_user)])
def get_users(db: Session = Depends(get_db)):
    people = db.query(models.DimUser).all()
    return people

@app.get("/categories/", response_model=List[schemas.Category], dependencies=[Depends(get_current_user)])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.DimCategory).all()
    return categories

@app.get("/payment_methods/", response_model=List[schemas.PaymentMethod], dependencies=[Depends(get_current_user)])
def get_payment_methods(db: Session = Depends(get_db)):
    payment_methods = db.query(models.DimPaymentMethod).all()
    return payment_methods

@app.get("/household_settings/", response_model=List[schemas.HouseholdSettingRead], dependencies=[Depends(get_current_user)])
def get_household_settings(db: Session = Depends(get_db)):
    settings = (
        db.query(models.HouseholdSetting)
        .options(joinedload(models.HouseholdSetting.user))
        .all()
    )
    return settings

@app.put("/household_settings/", response_model=List[schemas.HouseholdSettingRead], dependencies=[Depends(get_current_user)])
def update_household_settings(payload: schemas.HouseholdSettingsUpdate, db: Session = Depends(get_db)):
    """
    Replaces the whole set of household shares in one transaction, so the
    table is never left mid-update with shares that don't sum to 1 (the
    Pydantic schema already checked that; this checks the user_ids are real).
    """
    user_ids = [item.user_id for item in payload.settings]
    if len(set(user_ids)) != len(user_ids):
        raise HTTPException(status_code=400, detail="Duplicate user_id in request")

    existing_count = db.query(models.DimUser).filter(models.DimUser.user_id.in_(user_ids)).count()
    if existing_count != len(user_ids):
        raise HTTPException(status_code=400, detail="One or more user_id values do not exist")

    db.query(models.HouseholdSetting).delete()
    for item in payload.settings:
        db.add(models.HouseholdSetting(user_id=item.user_id, share_pct=item.share_pct))
    db.commit()

    return (
        db.query(models.HouseholdSetting)
        .options(joinedload(models.HouseholdSetting.user))
        .all()
    )

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

@app.get("/balances/", response_model=schemas.BalanceReport, dependencies=[Depends(get_current_user)])
def get_balances(
    month: str | None = Query(None, pattern=MONTH_PATTERN, description="YYYY-MM; omit for all time"),
    db: Session = Depends(get_db),
):
    """
    Net position per household member over shared expenses, and the
    transfer(s) that would settle it.

    "Shared" here means the expense has an allocation row for someone other
    than the payer. Personal expenses would net to zero anyway, and leaving
    them out keeps one person's private spending totals out of the other's view.
    Months are calendar months in America/Sao_Paulo, matching the ETL.
    """
    fact = models.FactExpenditure
    split = models.FactExpenditureSplit

    shared_ids = (
        db.query(split.expenditure_id)
        .join(fact, fact.expenditure_id == split.expenditure_id)
        .filter(split.user_id != fact.user_id)
    )
    if month:
        local_month = func.to_char(func.timezone("America/Sao_Paulo", fact.transaction_timestamp), "YYYY-MM")
        shared_ids = shared_ids.filter(local_month == month)
    shared_ids = shared_ids.distinct().subquery()

    paid = dict(
        db.query(fact.user_id, func.sum(fact.price))
        .filter(fact.expenditure_id.in_(select(shared_ids)))
        .group_by(fact.user_id)
        .all()
    )
    borne = dict(
        db.query(split.user_id, func.sum(split.share_amount))
        .filter(split.expenditure_id.in_(select(shared_ids)))
        .group_by(split.user_id)
        .all()
    )

    # Everyone in the household ratio, plus anyone who appears in the period.
    member_ids = {row.user_id for row in db.query(models.HouseholdSetting.user_id)} | paid.keys() | borne.keys()
    names = dict(
        db.query(models.DimUser.user_id, models.DimUser.full_name)
        .filter(models.DimUser.user_id.in_(member_ids))
        .all()
    )

    zero = Decimal("0.00")
    members = []
    for uid in sorted(member_ids):
        p, b = paid.get(uid, zero), borne.get(uid, zero)
        members.append(schemas.MemberBalance(user_id=uid, full_name=names.get(uid), paid=p, borne=b, net=p - b))

    transfers = [
        schemas.Transfer(
            from_user_id=src, from_name=names.get(src),
            to_user_id=dst, to_name=names.get(dst),
            amount=amount,
        )
        for src, dst, amount in settle({m.user_id: m.net for m in members})
    ]

    return schemas.BalanceReport(month=month, members=members, transfers=transfers)

@app.get("/summary/", response_model=schemas.MonthlySummary)
def get_summary(
    month: str | None = Query(None, pattern=MONTH_PATTERN, description="YYYY-MM; defaults to the current month"),
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user),
):
    """
    The logged-in user's spending for a month and the one before it: what
    they bear (their share of shared expenses plus their personal ones),
    broken down by category and cost type, plus the household's shared total.

    Uses the same definition of "shared" as /balances/ (a split row for
    someone other than the payer) and São Paulo calendar months.
    """
    if month is None:
        month = datetime.now(SAO_PAULO).strftime("%Y-%m")
    year, mon = int(month[:4]), int(month[5:])
    previous = f"{year - 1}-12" if mon == 1 else f"{year}-{mon - 1:02d}"

    fact = models.FactExpenditure
    split = models.FactExpenditureSplit
    category = models.DimCategory

    local_month = func.to_char(func.timezone("America/Sao_Paulo", fact.transaction_timestamp), "YYYY-MM")
    other = aliased(models.FactExpenditureSplit)
    is_shared = exists().where(other.expenditure_id == fact.expenditure_id, other.user_id != fact.user_id)

    # My allocation rows in both months, pre-aggregated.
    mine = (
        db.query(
            local_month.label("month"),
            is_shared.label("shared"),
            func.coalesce(category.primary_category, "Uncategorised").label("category"),
            func.coalesce(category.cost_type, "Unknown").label("cost_type"),
            func.sum(split.share_amount).label("amount"),
        )
        .join(fact, fact.expenditure_id == split.expenditure_id)
        .outerjoin(category, category.category_id == fact.category_id)
        .filter(split.user_id == current_user.user_id, local_month.in_([month, previous]))
        .group_by("month", "shared", "category", "cost_type")
        .all()
    )

    # Full price of shared expenses in both months, whoever paid.
    household = dict(
        db.query(local_month, func.sum(fact.price))
        .filter(is_shared, local_month.in_([month, previous]))
        .group_by(local_month)
        .all()
    )

    zero = Decimal("0.00")
    shared_share = personal = previous_total = zero
    by_category: dict[str, Decimal] = {}
    by_cost_type: dict[str, Decimal] = {}
    for row in mine:
        if row.month == previous:
            previous_total += row.amount
            continue
        if row.shared:
            shared_share += row.amount
        else:
            personal += row.amount
        by_category[row.category] = by_category.get(row.category, zero) + row.amount
        by_cost_type[row.cost_type] = by_cost_type.get(row.cost_type, zero) + row.amount

    def ranked(totals):
        return [schemas.AmountBy(label=k, amount=v) for k, v in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]

    return schemas.MonthlySummary(
        month=month,
        previous_month=previous,
        me=schemas.MySpending(
            total=shared_share + personal,
            previous_total=previous_total,
            shared_share=shared_share,
            personal=personal,
        ),
        household_shared=schemas.HouseholdShared(
            total=household.get(month, zero),
            previous_total=household.get(previous, zero),
        ),
        by_category=ranked(by_category),
        by_cost_type=ranked(by_cost_type),
    )

# --- Delete Endpoints ---

@app.delete("/users/{user_id}", dependencies=[Depends(get_current_user)])
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

@app.delete("/categories/{category_id}", dependencies=[Depends(get_current_user)])
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

@app.delete("/payment_methods/{payment_method_id}", dependencies=[Depends(get_current_user)])
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

@app.post("/refresh", dependencies=[Depends(get_current_user)])
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