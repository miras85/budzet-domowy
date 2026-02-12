from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, timedelta
import models, database, auth
from pydantic import BaseModel

# Inicjalizacja bazy
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

print("--- SYSTEM STARTUP: WERSJA Z LOGOWANIEM ---")

# --- ZABEZPIECZENIA ---
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nieprawidłowe dane logowania",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except auth.JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# --- STARTUP: TWORZENIE ADMINA ---
@app.on_event("startup")
def create_default_user():
    db = database.SessionLocal()
    user = db.query(models.User).filter(models.User.username == "admin").first()
    if not user:
        print("--- TWORZENIE UŻYTKOWNIKA ADMIN ---")
        hashed_pwd = auth.get_password_hash("admin")
        new_user = models.User(username="admin", hashed_password=hashed_pwd)
        db.add(new_user)
        db.commit()
    db.close()

# --- DTO ---
class TransactionCreate(BaseModel):
    amount: float
    description: str
    date: date
    type: str
    account_id: int
    target_account_id: Optional[int] = None
    category_name: Optional[str] = None
    loan_id: Optional[int] = None
    status: str = "zrealizowana"

class AccountUpdate(BaseModel):
    name: str
    type: str
    balance: float
    is_savings: bool = False

class LoanCreate(BaseModel):
    name: str
    total_amount: float
    remaining_amount: float
    monthly_payment: float
    next_payment_date: date

class LoanUpdate(BaseModel):
    name: str
    total_amount: float
    remaining_amount: float
    monthly_payment: float
    next_payment_date: date

class PaydayOverrideCreate(BaseModel):
    year: int
    month: int
    day: int

class CategoryCreate(BaseModel):
    name: str

class GoalCreate(BaseModel):
    name: str
    target_amount: float
    deadline: date
    account_id: int  # Nowe wymagane pole

class GoalFund(BaseModel):
    amount: float
    source_account_id: int
    target_savings_id: Optional[int] = None

class GoalTransfer(BaseModel):
    amount: float
    target_goal_id: int
    
class UserCreate(BaseModel):
    username: str
    password: str

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

# --- LOGIKA DAT ---
def get_actual_payday(year, month, db: Session):
    override = db.query(models.PaydayOverride).filter(models.PaydayOverride.year == year, models.PaydayOverride.month == month).first()
    if override: return date(year, month, override.day)
    try: base_date = date(year, month, 25)
    except ValueError: base_date = date(year, month, 1) + timedelta(days=27)
    weekday = base_date.weekday()
    if weekday == 5: return base_date - timedelta(days=1)
    elif weekday == 6: return base_date - timedelta(days=2)
    return base_date

def get_billing_period(db: Session, offset: int = 0):
    today = date.today()
    current_month_payday = get_actual_payday(today.year, today.month, db)
    if today < current_month_payday:
        base_month = today.month - 1
        base_year = today.year
        if base_month < 1: base_month = 12; base_year -= 1
    else:
        base_month = today.month
        base_year = today.year
    target_month = base_month + offset
    target_year = base_year
    while target_month > 12: target_month -= 12; target_year += 1
    while target_month < 1: target_month += 12; target_year -= 1
    start_date = get_actual_payday(target_year, target_month, db)
    next_m = target_month + 1
    next_y = target_year
    if next_m > 12: next_m = 1; next_y += 1
    next_payday = get_actual_payday(next_y, next_m, db)
    end_date = next_payday - timedelta(days=1)
    return start_date, end_date

# --- POMOCNICZE ---
def update_balance(db, account_id, amount, type, target_id, is_reversal):
    acc = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not acc: return
    val = float(amount)
    if is_reversal: val = -val
    if type == 'income': acc.balance = float(acc.balance) + val
    elif type == 'expense': acc.balance = float(acc.balance) - val
    elif type == 'transfer':
        acc.balance = float(acc.balance) - val
        if target_id:
            acc_target = db.query(models.Account).filter(models.Account.id == target_id).first()
            if acc_target: acc_target.balance = float(acc_target.balance) + val

def update_loan_balance(db, loan_id, amount, is_reversal):
    if not loan_id: return
    loan = db.query(models.Loan).filter(models.Loan.id == loan_id).first()
    if not loan: return
    val = float(amount)
    if is_reversal: loan.remaining_amount = float(loan.remaining_amount) + val
    else: loan.remaining_amount = float(loan.remaining_amount) - val

# --- API LOGOWANIA ---
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Błędny login lub hasło",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- API (ZABEZPIECZONE) ---

@app.get("/api/dashboard")
def get_dashboard(offset: int = 0, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    start_date, end_date = get_billing_period(db, offset)
    
    def get_sum(query_filter):
        result = db.query(func.sum(models.Transaction.amount)).filter(query_filter).scalar()
        return float(result) if result is not None else 0.0

    raw_total = db.query(func.sum(models.Account.balance)).scalar()
    total_balance = float(raw_total) if raw_total is not None else 0.0
    
    raw_debt = db.query(func.sum(models.Loan.remaining_amount)).scalar()
    total_debt = float(raw_debt) if raw_debt is not None else 0.0
    
    inc_realized = get_sum((models.Transaction.type == 'income') & (models.Transaction.status == 'zrealizowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    inc_planned = get_sum((models.Transaction.type == 'income') & (models.Transaction.status == 'planowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    
    exp_realized = get_sum((models.Transaction.type == 'expense') & (models.Transaction.status == 'zrealizowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    exp_planned = get_sum((models.Transaction.type == 'expense') & (models.Transaction.status == 'planowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))

    goals = db.query(models.Goal).filter(models.Goal.is_archived == False).all()
    goals_monthly_need = 0.0
    goals_total_saved = 0.0
    
    for g in goals:
        current = float(g.current_amount)
        target = float(g.target_amount)
        goals_total_saved += current
        remaining = target - current
        if remaining > 0:
            cycles_left = 1
            check_offset = 0
            while True:
                _, cycle_end = get_billing_period(db, check_offset)
                if cycle_end >= g.deadline: break
                cycles_left += 1
                check_offset += 1
                if cycles_left > 120: break
            goals_monthly_need += (remaining / cycles_left)

    recent = db.query(models.Transaction).filter(models.Transaction.date >= start_date, models.Transaction.date <= end_date).order_by(models.Transaction.date.desc()).all()
    
    tx_list = []
    for t in recent:
        cat_name = t.category.name if t.category else "-"
        if t.type == 'transfer': cat_name = "Transfer"
        if t.loan_id:
            loan = db.query(models.Loan).filter(models.Loan.id == t.loan_id).first()
            if loan: cat_name = f"Spłata: {loan.name}"

        tx_list.append({
            "id": t.id, "desc": t.description, "amount": float(t.amount),
            "type": t.type, "category": cat_name, "date": str(t.date),
            "account_id": t.account_id, "target_account_id": t.target_account_id,
            "category_name": cat_name, "status": t.status,
            "loan_id": t.loan_id
        })

    return {
        "total_balance": total_balance,
        "total_debt": total_debt,
        "monthly_income_realized": inc_realized,
        "monthly_income_forecast": inc_realized + inc_planned,
        "monthly_expenses_realized": exp_realized,
        "monthly_expenses_forecast": exp_realized + exp_planned,
        "goals_monthly_need": goals_monthly_need,
        "goals_total_saved": goals_total_saved,
        "recent_transactions": tx_list,
        "period_start": str(start_date),
        "period_end": str(end_date)
    }

@app.get("/api/stats/trend")
def get_trend(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    data = []
    for i in range(5, -1, -1):
        offset = -i
        start, end = get_billing_period(db, offset)
        raw_inc = db.query(func.sum(models.Transaction.amount)).filter(models.Transaction.type == 'income', models.Transaction.status == 'zrealizowana', models.Transaction.date >= start, models.Transaction.date <= end).scalar()
        raw_exp = db.query(func.sum(models.Transaction.amount)).filter(models.Transaction.type == 'expense', models.Transaction.status == 'zrealizowana', models.Transaction.date >= start, models.Transaction.date <= end).scalar()
        inc = float(raw_inc) if raw_inc is not None else 0.0
        exp = float(raw_exp) if raw_exp is not None else 0.0
        months = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"]
        label = f"{months[start.month - 1]}"
        data.append({"label": label, "income": inc, "expense": exp})
    return data

@app.post("/api/transactions")
def add_transaction(tx: TransactionCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    cat_id = None
    if tx.type != 'transfer' and tx.category_name:
        cat = db.query(models.Category).filter(models.Category.name == tx.category_name).first()
        if not cat:
            cat = models.Category(name=tx.category_name)
            db.add(cat)
            db.commit()
        cat_id = cat.id
    new_tx = models.Transaction(amount=tx.amount, description=tx.description, date=tx.date, type=tx.type, account_id=tx.account_id, category_id=cat_id, status=tx.status, target_account_id=tx.target_account_id, loan_id=tx.loan_id)
    db.add(new_tx)
    if tx.status == 'zrealizowana':
        update_balance(db, tx.account_id, tx.amount, tx.type, tx.target_account_id, is_reversal=False)
        if tx.loan_id and tx.type == 'expense': update_loan_balance(db, tx.loan_id, tx.amount, is_reversal=False)
    db.commit()
    return {"status": "added"}

@app.put("/api/transactions/{tx_id}")
def update_transaction(tx_id: int, tx_data: TransactionCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    old_tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not old_tx: raise HTTPException(status_code=404)
    if old_tx.status == 'zrealizowana':
        update_balance(db, old_tx.account_id, old_tx.amount, old_tx.type, old_tx.target_account_id, is_reversal=True)
        if old_tx.loan_id and old_tx.type == 'expense': update_loan_balance(db, old_tx.loan_id, old_tx.amount, is_reversal=True)
    cat_id = None
    if tx_data.type != 'transfer' and tx_data.category_name:
        cat = db.query(models.Category).filter(models.Category.name == tx_data.category_name).first()
        if not cat:
            cat = models.Category(name=tx_data.category_name)
            db.add(cat)
            db.commit()
        cat_id = cat.id
    old_tx.amount = tx_data.amount; old_tx.description = tx_data.description; old_tx.date = tx_data.date
    old_tx.type = tx_data.type; old_tx.account_id = tx_data.account_id; old_tx.target_account_id = tx_data.target_account_id
    old_tx.category_id = cat_id; old_tx.status = tx_data.status; old_tx.loan_id = tx_data.loan_id
    if tx_data.status == 'zrealizowana':
        update_balance(db, tx_data.account_id, tx_data.amount, tx_data.type, tx_data.target_account_id, is_reversal=False)
        if tx_data.loan_id and tx_data.type == 'expense': update_loan_balance(db, tx_data.loan_id, tx_data.amount, is_reversal=False)
    db.commit()
    return {"status": "updated"}

@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not tx: raise HTTPException(status_code=404)
    if tx.status == 'zrealizowana':
        update_balance(db, tx.account_id, tx.amount, tx.type, tx.target_account_id, is_reversal=True)
        if tx.loan_id and tx.type == 'expense': update_loan_balance(db, tx.loan_id, tx.amount, is_reversal=True)
    db.delete(tx); db.commit(); return {"status": "deleted"}

@app.get("/api/goals")
def get_goals(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): return db.query(models.Goal).filter(models.Goal.is_archived == False).all()
@app.post("/api/goals")
def create_goal(goal: GoalCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    # Sprawdź czy konto istnieje i czy jest oszczędnościowe
    acc = db.query(models.Account).filter(models.Account.id == goal.account_id).first()
    if not acc or not acc.is_savings:
        raise HTTPException(status_code=400, detail="Cel musi być przypisany do konta oszczędnościowego")
    
    db.add(models.Goal(**goal.dict()))
    db.commit()
    return {"status": "ok"}
@app.post("/api/goals/{goal_id}/fund")
def fund_goal(goal_id: int, fund: GoalFund, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal: raise HTTPException(status_code=404)
    
    source_acc = db.query(models.Account).filter(models.Account.id == fund.source_account_id).first()
    if not source_acc: raise HTTPException(status_code=404, detail="Brak konta źródłowego")

    # SCENARIUSZ 1: Przelew z ROR (Automatyczny Transfer)
    if not source_acc.is_savings:
        if not fund.target_savings_id:
            raise HTTPException(status_code=400, detail="Wymagane wskazanie konta oszczędnościowego dla transferu")
        
        target_acc = db.query(models.Account).filter(models.Account.id == fund.target_savings_id).first()
        if not target_acc or not target_acc.is_savings:
            raise HTTPException(status_code=400, detail="Konto docelowe musi być oszczędnościowe")

        # 1. Tworzymy transakcję transferu
        transfer_tx = models.Transaction(
            amount=fund.amount,
            description=f"Zasilenie celu: {goal.name}",
            date=date.today(),
            type="transfer",
            account_id=source_acc.id,
            target_account_id=target_acc.id,
            status="zrealizowana"
        )
        db.add(transfer_tx)
        
        # 2. Aktualizujemy salda (ROR - kwota, Oszcz + kwota)
        update_balance(db, source_acc.id, fund.amount, "transfer", target_acc.id, is_reversal=False)
    
    # SCENARIUSZ 2: Pieniądze już są na koncie oszczędnościowym (tylko przypisujemy do celu)
    # (W tym przypadku zakładamy, że środki już tam są, więc nie robimy transferu, tylko aktualizujemy cel)
    
    # 3. Aktualizujemy cel
    goal.current_amount = float(goal.current_amount) + fund.amount
    db.commit()
    
    return {"status": "funded"}
    
@app.post("/api/goals/{goal_id}/transfer")
def transfer_goal_funds(goal_id: int, transfer: GoalTransfer, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    source = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    target = db.query(models.Goal).filter(models.Goal.id == transfer.target_goal_id).first()
    if not source or not target: raise HTTPException(status_code=404)
    if float(source.current_amount) < transfer.amount: raise HTTPException(status_code=400, detail="Brak środków")
    source.current_amount = float(source.current_amount) - transfer.amount; target.current_amount = float(target.current_amount) + transfer.amount; db.commit(); return {"status": "transferred"}
@app.delete("/api/goals/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): db.query(models.Goal).filter(models.Goal.id == goal_id).delete(); db.commit(); return {"status": "deleted"}

@app.get("/api/loans")
def get_loans(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    loans = db.query(models.Loan).order_by(models.Loan.next_payment_date).all()
    today = date.today(); limit_date = today + timedelta(days=30); upcoming = []; all_loans = []
    for l in loans:
        if l.remaining_amount > 0 and l.next_payment_date >= today and l.next_payment_date <= limit_date: upcoming.append({"name": l.name, "amount": float(l.monthly_payment), "date": str(l.next_payment_date)})
        all_loans.append({"id": l.id, "name": l.name, "total": float(l.total_amount), "remaining": float(l.remaining_amount), "monthly": float(l.monthly_payment), "next_date": str(l.next_payment_date)})
    return {"loans": all_loans, "upcoming": upcoming}
@app.post("/api/loans")
def create_loan(loan: LoanCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): db_loan = models.Loan(**loan.dict()); db.add(db_loan); db.commit(); return {"status": "ok"}
@app.put("/api/loans/{loan_id}")
def update_loan(loan_id: int, loan: LoanUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    db_loan = db.query(models.Loan).filter(models.Loan.id == loan_id).first()
    if not db_loan: raise HTTPException(status_code=404)
    db_loan.name = loan.name; db_loan.total_amount = loan.total_amount; db_loan.remaining_amount = loan.remaining_amount; db_loan.monthly_payment = loan.monthly_payment; db_loan.next_payment_date = loan.next_payment_date; db.commit(); return {"status": "updated"}
@app.get("/api/categories")
def get_categories(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): return db.query(models.Category).order_by(models.Category.name).all()
@app.post("/api/categories")
def create_category(cat: CategoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    if db.query(models.Category).filter(models.Category.name == cat.name).first(): raise HTTPException(status_code=400, detail="Kategoria istnieje")
    db.add(models.Category(name=cat.name)); db.commit(); return {"status": "ok"}
@app.put("/api/categories/{cat_id}")
def update_category(cat_id: int, cat: CategoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    db_cat = db.query(models.Category).filter(models.Category.id == cat_id).first(); db_cat.name = cat.name; db.commit(); return {"status": "updated"}
@app.delete("/api/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): db.query(models.Category).filter(models.Category.id == cat_id).delete(); db.commit(); return {"status": "deleted"}
@app.get("/api/settings/payday-overrides")
def get_payday_overrides(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): return db.query(models.PaydayOverride).order_by(models.PaydayOverride.year.desc(), models.PaydayOverride.month.desc()).all()
@app.post("/api/settings/payday-overrides")
def add_payday_override(ov: PaydayOverrideCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.PaydayOverride).filter(models.PaydayOverride.year == ov.year, models.PaydayOverride.month == ov.month).first()
    if existing: existing.day = ov.day
    else: db.add(models.PaydayOverride(year=ov.year, month=ov.month, day=ov.day))
    db.commit(); return {"status": "ok"}
@app.delete("/api/settings/payday-overrides/{id}")
def delete_payday_override(id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): db.query(models.PaydayOverride).filter(models.PaydayOverride.id == id).delete(); db.commit(); return {"status": "deleted"}
@app.put("/api/accounts/{account_id}")
def update_account(account_id: int, acc: AccountUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    db_acc = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not db_acc: raise HTTPException(status_code=404)
    db_acc.name = acc.name; db_acc.type = acc.type; db_acc.balance = acc.balance; db_acc.is_savings = acc.is_savings; db.commit(); return {"status": "updated"}
@app.get("/api/accounts")
def get_accounts(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): return db.query(models.Account).all()
@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): db.query(models.Transaction).filter(models.Transaction.account_id == account_id).delete(); db.query(models.Account).filter(models.Account.id == account_id).delete(); db.commit(); return {"status": "deleted"}
@app.post("/api/accounts")
def create_account(acc: AccountUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)): db_acc = models.Account(name=acc.name, type=acc.type, balance=acc.balance, is_savings=acc.is_savings); db.add(db_acc); db.commit(); return {"status": "ok"}

@app.post("/api/users")
def create_user(user: UserCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    # Sprawdź czy użytkownik już istnieje
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Taki użytkownik już istnieje")
    
    # Zahaszuj hasło i zapisz
    hashed_pwd = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    return {"status": "created", "user": user.username}

@app.post("/api/users/change-password")
def change_password(pwd: PasswordChange, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    # Sprawdź stare hasło
    if not auth.verify_password(pwd.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Stare hasło jest nieprawidłowe")
    
    # Zapisz nowe
    current_user.hashed_password = auth.get_password_hash(pwd.new_password)
    db.commit()
    return {"status": "password_changed"}


app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
async def read_index(): return FileResponse('static/index.html')
