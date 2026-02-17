from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from typing import Optional
import database, models, schemas, utils
from services import dashboard, transaction, goal as goal_service, bank_import

router = APIRouter(prefix="/api", tags=["Finance"])

# --- IMPORT CSV ---
@router.post("/import/preview")
async def preview_import(file: UploadFile = File(...), db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    return await bank_import.parse_bank_csv(db, file)

@router.post("/import/confirm")
def confirm_import(data: schemas.ImportConfirm, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    return bank_import.save_imported_transactions(db, data.account_id, data.transactions)

# --- DASHBOARD & STATS ---
@router.get("/dashboard")
def get_dashboard(offset: int = 0, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    return dashboard.get_dashboard_data(db, offset)

@router.get("/stats/trend")
def get_trend(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    return dashboard.get_trend_data(db)

# --- TRANSAKCJE ---
@router.post("/transactions")
def add_transaction(tx: schemas.TransactionCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    transaction.create_transaction(db, tx)
    return {"status": "added"}

@router.put("/transactions/{tx_id}")
def update_transaction(tx_id: int, tx_data: schemas.TransactionCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    transaction.update_transaction(db, tx_id, tx_data)
    return {"status": "updated"}

@router.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    transaction.delete_transaction(db, tx_id)
    return {"status": "deleted"}

@router.get("/transactions/search")
def search_transactions(
    q: Optional[str] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
    category_id: Optional[int] = None, account_id: Optional[int] = None, type: Optional[str] = None,
    min_amount: Optional[float] = None, max_amount: Optional[float] = None,
    db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)
):
    return transaction.search_transactions(db, q, date_from, date_to, category_id, account_id, type, min_amount, max_amount)

# --- CELE ---
@router.get("/goals")
def get_goals(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    goals = db.query(models.Goal).filter(models.Goal.is_archived == False).all()
    start_date, end_date = utils.get_billing_period(db, 0)
    result = []
    for g in goals:
        goal_data = {"id": g.id, "name": g.name, "target_amount": float(g.target_amount), "current_amount": float(g.current_amount), "deadline": str(g.deadline), "account_id": g.account_id, "monthly_need": 0.0}
        remaining = float(g.target_amount) - float(g.current_amount)
        if remaining > 0:
            cycles_left = 1; check_offset = 0
            while True:
                _, cycle_end = utils.get_billing_period(db, check_offset)
                if cycle_end >= g.deadline: break
                cycles_left += 1; check_offset += 1
                if cycles_left > 120: break
            contribs = db.query(func.sum(models.GoalContribution.amount)).filter(models.GoalContribution.goal_id == g.id, models.GoalContribution.date >= start_date, models.GoalContribution.date <= end_date).scalar()
            paid_this_cycle = float(contribs) if contribs else 0.0
            virtual_start_amount = float(g.current_amount) - paid_this_cycle
            total_missing_at_start = float(g.target_amount) - virtual_start_amount
            rate_per_cycle = total_missing_at_start / cycles_left
            actual_need = rate_per_cycle - paid_this_cycle
            if actual_need < 0: actual_need = 0.0
            goal_data["monthly_need"] = actual_need
        result.append(goal_data)
    return result

@router.post("/goals")
def create_goal(goal: schemas.GoalCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    acc = db.query(models.Account).filter(models.Account.id == goal.account_id).first()
    if not acc or not acc.is_savings: raise HTTPException(status_code=400, detail="Cel musi być przypisany do konta oszczędnościowego")
    db.add(models.Goal(**goal.dict())); db.commit(); return {"status": "ok"}

@router.post("/goals/{goal_id}/fund")
def fund_goal(goal_id: int, fund: schemas.GoalFund, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    goal_service.fund_goal(db, goal_id, fund)
    return {"status": "funded"}

@router.post("/goals/{goal_id}/withdraw")
def withdraw_goal_funds(goal_id: int, withdraw: schemas.GoalWithdraw, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    goal_service.withdraw_goal(db, goal_id, withdraw)
    return {"status": "withdrawn"}

@router.post("/goals/{goal_id}/transfer")
def transfer_goal_funds(goal_id: int, transfer: schemas.GoalTransfer, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    goal_service.transfer_goal(db, goal_id, transfer)
    return {"status": "transferred"}

@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db.query(models.Goal).filter(models.Goal.id == goal_id).delete(); db.commit(); return {"status": "deleted"}

# --- POZOSTAŁE ---
@router.get("/loans")
def get_loans(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    loans = db.query(models.Loan).order_by(models.Loan.next_payment_date).all()
    today = date.today(); limit_date = today + timedelta(days=30); upcoming = []; all_loans = []
    for l in loans:
        if l.remaining_amount > 0 and l.next_payment_date >= today and l.next_payment_date <= limit_date: upcoming.append({"name": l.name, "amount": float(l.monthly_payment), "date": str(l.next_payment_date)})
        all_loans.append({"id": l.id, "name": l.name, "total": float(l.total_amount), "remaining": float(l.remaining_amount), "monthly": float(l.monthly_payment), "next_date": str(l.next_payment_date)})
    return {"loans": all_loans, "upcoming": upcoming}
@router.post("/loans")
def create_loan(loan: schemas.LoanCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db_loan = models.Loan(**loan.dict()); db.add(db_loan); db.commit(); return {"status": "ok"}
@router.put("/loans/{loan_id}")
def update_loan(loan_id: int, loan: schemas.LoanUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db_loan = db.query(models.Loan).filter(models.Loan.id == loan_id).first()
    if not db_loan: raise HTTPException(status_code=404)
    db_loan.name = loan.name; db_loan.total_amount = loan.total_amount; db_loan.remaining_amount = loan.remaining_amount; db_loan.monthly_payment = loan.monthly_payment; db_loan.next_payment_date = loan.next_payment_date; db.commit(); return {"status": "updated"}
@router.get("/categories")
def get_categories(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): return db.query(models.Category).order_by(models.Category.name).all()
@router.post("/categories")
def create_category(cat: schemas.CategoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    if db.query(models.Category).filter(models.Category.name == cat.name).first(): raise HTTPException(status_code=400, detail="Kategoria istnieje")
    db.add(models.Category(name=cat.name, monthly_limit=cat.monthly_limit)); db.commit(); return {"status": "ok"}
@router.put("/categories/{cat_id}")
def update_category(cat_id: int, cat: schemas.CategoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db_cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    db_cat.name = cat.name; db_cat.monthly_limit = cat.monthly_limit; db.commit(); return {"status": "updated"}
@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db.query(models.Category).filter(models.Category.id == cat_id).delete(); db.commit(); return {"status": "deleted"}
@router.get("/settings/payday-overrides")
def get_payday_overrides(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): return db.query(models.PaydayOverride).order_by(models.PaydayOverride.year.desc(), models.PaydayOverride.month.desc()).all()
@router.post("/settings/payday-overrides")
def add_payday_override(ov: schemas.PaydayOverrideCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    existing = db.query(models.PaydayOverride).filter(models.PaydayOverride.year == ov.year, models.PaydayOverride.month == ov.month).first()
    if existing: existing.day = ov.day
    else: db.add(models.PaydayOverride(year=ov.year, month=ov.month, day=ov.day))
    db.commit(); return {"status": "ok"}
@router.delete("/settings/payday-overrides/{id}")
def delete_payday_override(id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db.query(models.PaydayOverride).filter(models.PaydayOverride.id == id).delete(); db.commit(); return {"status": "deleted"}
@router.put("/accounts/{account_id}")
def update_account(account_id: int, acc: schemas.AccountUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db_acc = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not db_acc: raise HTTPException(status_code=404)
    db_acc.name = acc.name; db_acc.type = acc.type; db_acc.balance = acc.balance; db_acc.is_savings = acc.is_savings; db.commit(); return {"status": "updated"}
@router.get("/accounts")
def get_accounts(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    accounts = db.query(models.Account).all()
    result = []
    for acc in accounts:
        reserved = 0.0
        if acc.is_savings:
            res_val = db.query(func.sum(models.Goal.current_amount)).filter(models.Goal.account_id == acc.id).scalar()
            reserved = float(res_val) if res_val else 0.0
        result.append({"id": acc.id, "name": acc.name, "type": acc.type, "balance": float(acc.balance), "is_savings": acc.is_savings, "available": float(acc.balance) - reserved})
    return result
@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db.query(models.Transaction).filter(models.Transaction.account_id == account_id).delete(); db.query(models.Account).filter(models.Account.id == account_id).delete(); db.commit(); return {"status": "deleted"}
@router.post("/accounts")
def create_account(acc: schemas.AccountUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db_acc = models.Account(name=acc.name, type=acc.type, balance=acc.balance, is_savings=acc.is_savings); db.add(db_acc); db.commit(); return {"status": "ok"}
