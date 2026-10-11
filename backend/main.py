from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from jose import JWTError , jwt
from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import exists, or_, func, select
from sqlalchemy.exc import IntegrityError
from typing import List
from decimal import Decimal
from split_logic import settle
from ledger import HouseholdNotConfigured, InvalidSplit, add_expenditure

from config import settings
from auth import verify_password, create_access_token, get_password_hash, hash_reset_token, new_reset_token, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from email_sender import EmailSender, get_email_sender, send_quietly


from pydantic import BaseModel
import models
import schemas
from database import SessionLocal
from etl.main import run_pipeline

app = FastAPI()

# Reporting months are calendar months in the household's timezone.
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def month_start(month: str) -> date:
    """'2026-10' -> date(2026, 10, 1)."""
    return date(int(month[:4]), int(month[5:]), 1)

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
    

def visible_to(user: models.DimUser):
    """
    The expenditures a user may see or delete: ones they paid, plus ones
    they hold a share of. Derived from allocation rows, so an account
    outside the household never sees the household's shared expenses.
    """
    mine = aliased(models.FactExpenditureSplit)
    return or_(
        models.FactExpenditure.user_id == user.user_id,
        exists().where(
            mine.expenditure_id == models.FactExpenditure.expenditure_id,
            mine.user_id == user.user_id,
        ),
    )


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
    # Remove user_id from the request JSON for fraud prevention, and
    # is_shared and shares, which are instructions for the split below
    # rather than stored columns.
    expenditure_data = expenditure.model_dump(exclude={"user_id", "is_shared", "shares"})
    shares = [(s.user_id, s.share_pct) for s in expenditure.shares] if expenditure.shares else None

    # The request's is_shared means "split this by the household ratio";
    # the allocation rows written by add_expenditure are what make it shared.
    try:
        db_expenditure = add_expenditure(
            db, current_user.user_id,  # force the logged-in user as payer
            expenditure_data, shared=expenditure.is_shared, shares=shares,
        )
    except HouseholdNotConfigured:
        # Nothing committed yet, so the flushed expenditure is rolled back too.
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Household split ratio is not configured. Set it on the Manage Settings page first.",
        )
    except InvalidSplit as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid split: {e}")

    # One commit, covering the expenditure and its allocation row(s) together.
    db.commit()
    db.refresh(db_expenditure)

    return db_expenditure


@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Public route: on a LAN install anyone who can reach the app could sign
    # up, so ALLOWED_SIGNUP_EMAILS can restrict it to the household.
    if not settings.signup_allowed(user.email):
        raise HTTPException(status_code=403, detail="Sign-up is restricted on this installation")

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


# --- Password reset (both routes are public: the user can't log in) ---

RESET_REQUESTED = "If that account exists, we've sent a reset link."
RESET_INVALID = "This reset link is invalid or has expired."
# Links one account may be sent per hour; requests beyond this send nothing.
RESET_MAX_PER_HOUR = 3


@app.post("/password-reset/request", status_code=202, response_model=schemas.Message)
def request_password_reset(
    payload: schemas.PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    """
    Emails a one-time reset link. Always answers 202 with the same body, so
    the response never reveals whether an account exists.
    """
    user = (
        db.query(models.DimUser)
        .filter(func.lower(models.DimUser.email) == payload.email.strip().lower())
        .first()
    )
    if user is None:
        return {"detail": RESET_REQUESTED}

    Token = models.PasswordResetToken
    recent = db.query(func.count(Token.id)).filter(
        Token.user_id == user.user_id,
        Token.created_at > func.now() - timedelta(hours=1),
    ).scalar()
    if recent >= RESET_MAX_PER_HOUR:
        return {"detail": RESET_REQUESTED}

    # Only the newest link works: retire any earlier unused ones.
    db.query(Token).filter(Token.user_id == user.user_id, Token.used_at.is_(None)).update(
        {Token.used_at: func.now()}, synchronize_session=False
    )
    raw_token = new_reset_token()
    expire_minutes = settings.password_reset_expire_minutes
    db.add(Token(
        user_id=user.user_id,
        token_hash=hash_reset_token(raw_token),
        expires_at=func.now() + timedelta(minutes=expire_minutes),
    ))
    db.commit()

    link = f"{settings.frontend_base_url.rstrip('/')}/?reset_token={raw_token}"
    body = (
        f"Hi {user.full_name or 'there'},\n\n"
        "Someone asked to reset the password for your Personal Finance account.\n"
        f"Open this link to choose a new one (it works once, for {expire_minutes} minutes):\n\n"
        f"{link}\n\n"
        "If it wasn't you, ignore this email; your password hasn't changed.\n"
    )
    # Sent after the response, so a slow SMTP server doesn't hold the request.
    background_tasks.add_task(send_quietly, sender, user.email, "Reset your Personal Finance password", body)
    return {"detail": RESET_REQUESTED}


@app.post("/password-reset/confirm", response_model=schemas.Message)
def confirm_password_reset(payload: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    """Redeems a reset token: sets the new password and burns the token, in one commit."""
    Token = models.PasswordResetToken
    reset = (
        db.query(Token)
        .filter(
            Token.token_hash == hash_reset_token(payload.token),
            Token.used_at.is_(None),
            Token.expires_at > func.now(),
        )
        # Locks the row, so two concurrent confirms can't both redeem it.
        .with_for_update()
        .first()
    )
    if reset is None:
        raise HTTPException(status_code=400, detail=RESET_INVALID)

    user = db.get(models.DimUser, reset.user_id)
    user.hashed_password = get_password_hash(payload.new_password)
    reset.used_at = func.now()
    db.commit()
    return {"detail": "Password updated. You can now log in."}


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
    The expenditures the current user paid or holds a share of (see visible_to),
    each with `my_share`: the current user's share_amount, 0 when they hold none.
    """
    expenditures = (
        db.query(models.FactExpenditure)
        .filter(visible_to(current_user))
        .options(
            joinedload(models.FactExpenditure.user),
            joinedload(models.FactExpenditure.category),
            joinedload(models.FactExpenditure.payment_method)
        )
        .all()
    )
    split = models.FactExpenditureSplit
    my_shares = dict(
        db.query(split.expenditure_id, split.share_amount)
        .filter(split.user_id == current_user.user_id,
                split.expenditure_id.in_([e.expenditure_id for e in expenditures]))
        .all()
    )
    for e in expenditures:
        # Read by ExpenditureRead.my_share; not a mapped column.
        e.my_share = my_shares.get(e.expenditure_id, Decimal("0.00"))
    return expenditures

@app.get("/balances/", response_model=schemas.BalanceReport, dependencies=[Depends(get_current_user)])
def get_balances(
    month: str | None = Query(None, pattern=MONTH_PATTERN, description="YYYY-MM; omit for all time"),
    db: Session = Depends(get_db),
):
    """
    Net position per household member over shared expenses, minus what has
    already been settled, and the transfer(s) that would settle the rest.

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

    # Settlements for the same period subtract out of the position:
    # paying someone back raises your net, receiving it lowers theirs.
    settlements = db.query(models.FactSettlement)
    if month:
        settlements = settlements.filter(models.FactSettlement.period_month == month_start(month))
    settled_out: dict[int, Decimal] = {}
    settled_in: dict[int, Decimal] = {}
    for s in settlements:
        settled_out[s.from_user_id] = settled_out.get(s.from_user_id, Decimal("0")) + s.amount
        settled_in[s.to_user_id] = settled_in.get(s.to_user_id, Decimal("0")) + s.amount

    # Everyone in the household ratio, plus anyone who appears in the period.
    member_ids = (
        {row.user_id for row in db.query(models.HouseholdSetting.user_id)}
        | paid.keys() | borne.keys() | settled_out.keys() | settled_in.keys()
    )
    names = dict(
        db.query(models.DimUser.user_id, models.DimUser.full_name)
        .filter(models.DimUser.user_id.in_(member_ids))
        .all()
    )

    zero = Decimal("0.00")
    members = []
    for uid in sorted(member_ids):
        p, b = paid.get(uid, zero), borne.get(uid, zero)
        out, inc = settled_out.get(uid, zero), settled_in.get(uid, zero)
        members.append(schemas.MemberBalance(
            user_id=uid, full_name=names.get(uid),
            paid=p, borne=b, settled_out=out, settled_in=inc,
            net=p - b + out - inc,
        ))

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
    is_shared = fact.has_other_share

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

# --- Settlements ---

def settlement_read(s: models.FactSettlement) -> schemas.SettlementRead:
    return schemas.SettlementRead(
        settlement_id=s.settlement_id,
        settled_at=s.settled_at,
        month=s.period_month.strftime("%Y-%m") if s.period_month else None,
        from_user_id=s.from_user_id, from_name=s.from_user.full_name,
        to_user_id=s.to_user_id, to_name=s.to_user.full_name,
        amount=s.amount,
        note=s.note,
    )


@app.post("/settlements/", response_model=schemas.SettlementRead)
def create_settlement(
    payload: schemas.SettlementCreate,
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user),
):
    """
    Records money moved between two household members. You can only record
    a payment you made or received.
    """
    if current_user.user_id not in (payload.from_user_id, payload.to_user_id):
        raise HTTPException(status_code=403, detail="You can only record a payment you made or received")

    found = db.query(models.DimUser).filter(
        models.DimUser.user_id.in_([payload.from_user_id, payload.to_user_id])
    ).count()
    if found != 2:
        raise HTTPException(status_code=400, detail="One or more user_id values do not exist")

    settlement = models.FactSettlement(
        settled_at=payload.settled_at,
        period_month=month_start(payload.month) if payload.month else None,
        from_user_id=payload.from_user_id,
        to_user_id=payload.to_user_id,
        amount=payload.amount,
        note=payload.note,
        recorded_by_user_id=current_user.user_id,
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement_read(settlement)


@app.get("/settlements/", response_model=List[schemas.SettlementRead], dependencies=[Depends(get_current_user)])
def get_settlements(
    month: str | None = Query(None, pattern=MONTH_PATTERN, description="YYYY-MM; omit for all"),
    db: Session = Depends(get_db),
):
    """Settlements, newest first; with `month`, only those squaring up that month."""
    query = (
        db.query(models.FactSettlement)
        .options(joinedload(models.FactSettlement.from_user), joinedload(models.FactSettlement.to_user))
    )
    if month:
        query = query.filter(models.FactSettlement.period_month == month_start(month))
    return [settlement_read(s) for s in query.order_by(models.FactSettlement.settled_at.desc()).all()]


@app.delete("/settlements/{settlement_id}")
def delete_settlement(
    settlement_id: int,
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user),
):
    """Deletes a settlement entered by mistake; only its payer or payee can."""
    settlement = (
        db.query(models.FactSettlement)
        .filter(models.FactSettlement.settlement_id == settlement_id)
        .filter(or_(
            models.FactSettlement.from_user_id == current_user.user_id,
            models.FactSettlement.to_user_id == current_user.user_id,
        ))
        .first()
    )
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found (or you don't have permission)")
    db.delete(settlement)
    db.commit()
    return {"message": "Settlement deleted"}

# --- Delete Endpoints ---

@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user),
):
    # An account can only delete itself, never another household member.
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own account.")

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
    Delete an expenditure the current user paid or holds a share of
    (see visible_to). Its allocation rows go with it (ON DELETE CASCADE).
    """
    exp = (
        db.query(models.FactExpenditure)
        .filter(models.FactExpenditure.expenditure_id == expenditure_id)
        .filter(visible_to(current_user))
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

# --- Shared-expense analytics ---
# The in-app Analytics "Overview": shared expenses only, seen through two
# lenses (the household's full price and the logged-in user's share).

# Imported here rather than at the top so this section stays self-contained.
import calendar
from sqlalchemy import case, extract


def shift_month(month: str, delta: int) -> str:
    """'2026-10', -1 -> '2026-09'; crosses year boundaries."""
    index = int(month[:4]) * 12 + int(month[5:]) - 1 + delta
    return f"{index // 12}-{index % 12 + 1:02d}"


# Privacy rule for both routes: an expense qualifies only when it is shared
# (FactExpenditure.has_other_share: someone other than the payer bears part
# of it) AND the current user either holds a split row for it or paid it —
# the same people visible_to() lets see it. The outer join on "my" split row
# supplies my share_amount, which is 0 for an expense I paid but put entirely
# on my partner ("this one's on her"). Personal expenses — mine or my
# partner's — never appear, and an account outside the household gets nothing.


@app.get("/analytics/shared", response_model=schemas.SharedAnalytics)
def get_shared_analytics(
    month: str | None = Query(None, pattern=MONTH_PATTERN, description="YYYY-MM, the last month of the window; defaults to the current month"),
    months: int = Query(12, ge=1, le=24, description="How many months the window covers, ending at `month`"),
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user),
):
    """
    Shared expenses per São Paulo month × category over a window of months,
    as the household's full price and as the current user's share.

    Each row also carries *_to_day totals, counting only days 1..as_of_day,
    so a month still in progress can be compared with the same days of the
    other months. Months with no shared expenses have no rows; `months`
    lists the whole window so the client can zero-fill.
    """
    today = datetime.now(SAO_PAULO)
    current = today.strftime("%Y-%m")
    if month is None:
        month = current
    window = [shift_month(month, -k) for k in range(months - 1, -1, -1)]
    is_partial = month == current
    as_of_day = today.day if is_partial else calendar.monthrange(int(month[:4]), int(month[5:]))[1]

    fact = models.FactExpenditure
    mine = models.FactExpenditureSplit
    category = models.DimCategory

    local_ts = func.timezone("America/Sao_Paulo", fact.transaction_timestamp)
    local_month = func.to_char(local_ts, "YYYY-MM")
    in_first_days = extract("day", local_ts) <= as_of_day

    rows = (
        db.query(
            local_month.label("month"),
            func.coalesce(category.primary_category, "Uncategorised").label("primary_category"),
            func.coalesce(category.sub_category, "Uncategorised").label("sub_category"),
            func.coalesce(category.cost_type, "Unknown").label("cost_type"),
            func.sum(fact.price).label("household"),
            func.sum(func.coalesce(mine.share_amount, 0)).label("mine"),
            func.count(fact.expenditure_id).label("count"),
            func.sum(case((in_first_days, fact.price), else_=0)).label("household_to_day"),
            func.sum(case((in_first_days, func.coalesce(mine.share_amount, 0)), else_=0)).label("mine_to_day"),
        )
        # One split row per (expense, user), so this join never duplicates a price.
        .outerjoin(mine, (mine.expenditure_id == fact.expenditure_id) & (mine.user_id == current_user.user_id))
        .outerjoin(category, category.category_id == fact.category_id)
        .filter(
            fact.has_other_share, local_month.in_(window),
            or_(mine.user_id.isnot(None), fact.user_id == current_user.user_id),
        )
        .group_by("month", "primary_category", "sub_category", "cost_type")
        .order_by("month", "primary_category", "sub_category")
        .all()
    )

    cents = Decimal("0.01")
    return schemas.SharedAnalytics(
        month=month,
        months=window,
        is_partial=is_partial,
        as_of_day=as_of_day,
        rows=[
            schemas.SharedAnalyticsRow(
                month=r.month,
                primary_category=r.primary_category,
                sub_category=r.sub_category,
                cost_type=r.cost_type,
                household=Decimal(r.household).quantize(cents),
                mine=Decimal(r.mine).quantize(cents),
                count=r.count,
                household_to_day=Decimal(r.household_to_day).quantize(cents),
                mine_to_day=Decimal(r.mine_to_day).quantize(cents),
            )
            for r in rows
        ],
    )


@app.get("/analytics/shared/expenses", response_model=List[schemas.SharedExpense])
def get_shared_expenses(
    month: str | None = Query(None, pattern=MONTH_PATTERN, description="YYYY-MM; defaults to the current month"),
    primary_category: str | None = Query(None, description="Only this primary category ('Uncategorised' for none)"),
    db: Session = Depends(get_db),
    current_user: models.DimUser = Depends(get_current_user),
):
    """
    The individual shared expenses behind /analytics/shared for one São Paulo
    month, newest first, optionally for one primary category. Same privacy
    rule: shared, and the current user holds a share of it.
    """
    if month is None:
        month = datetime.now(SAO_PAULO).strftime("%Y-%m")

    fact = models.FactExpenditure
    mine = models.FactExpenditureSplit
    category = models.DimCategory
    method = models.DimPaymentMethod
    payer = models.DimUser

    local_month = func.to_char(func.timezone("America/Sao_Paulo", fact.transaction_timestamp), "YYYY-MM")
    primary = func.coalesce(category.primary_category, "Uncategorised")

    query = (
        db.query(
            fact.expenditure_id,
            fact.transaction_timestamp,
            primary.label("primary_category"),
            func.coalesce(category.sub_category, "Uncategorised").label("sub_category"),
            func.coalesce(category.cost_type, "Unknown").label("cost_type"),
            method.method_name.label("payment_method"),
            method.institution,
            payer.full_name.label("paid_by"),
            fact.price,
            func.coalesce(mine.share_amount, 0).label("mine"),
            func.coalesce(mine.share_pct, 0).label("share_pct"),
            fact.current_installment,
            fact.total_installments,
            fact.nature,
        )
        .outerjoin(mine, (mine.expenditure_id == fact.expenditure_id) & (mine.user_id == current_user.user_id))
        .join(payer, payer.user_id == fact.user_id)
        .outerjoin(category, category.category_id == fact.category_id)
        .outerjoin(method, method.payment_method_id == fact.payment_method_id)
        .filter(
            fact.has_other_share, local_month == month,
            or_(mine.user_id.isnot(None), fact.user_id == current_user.user_id),
        )
    )
    if primary_category is not None:
        query = query.filter(primary == primary_category)

    rows = query.order_by(fact.transaction_timestamp.desc(), fact.expenditure_id.desc()).all()
    return [schemas.SharedExpense(**r._mapping) for r in rows]
