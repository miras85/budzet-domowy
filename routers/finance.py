### routers/finance.py
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
    data = dashboard.get_dashboard_data(db, offset)
    # Uzupełniamy transakcje o ikony i kolory
    for tx in data["recent_transactions"]:
        if tx["category_name"] and tx["category_name"] != "-" and tx["category_name"] != "Transfer":
            cat = db.query(models.Category).filter(models.Category.name == tx["category_name"]).first()
            if cat:
                tx["category_icon"] = cat.icon_name
                tx["category_color"] = cat.color
    return data

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
    result = transaction.search_transactions(db, q, date_from, date_to, category_id, account_id, type, min_amount, max_amount)
    for tx in result["transactions"]:
        if tx["category"] and tx["category"] != "-" and tx["category"] != "Transfer":
            cat = db.query(models.Category).filter(models.Category.name == tx["category"]).first()
            if cat:
                tx["category_icon"] = cat.icon_name
                tx["category_color"] = cat.color
    return result

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
    
    
@router.put("/goals/{goal_id}")
def update_goal(goal_id: int, goal_data: schemas.GoalUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db_goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail="Cel nie istnieje")
    
    db_goal.name = goal_data.name
    db_goal.target_amount = goal_data.target_amount
    db_goal.deadline = goal_data.deadline
    db_goal.account_id = goal_data.account_id
    
    db.commit()
    return {"status": "updated"}

@router.post("/goals/{goal_id}/transfer")
def transfer_goal_funds(goal_id: int, transfer: schemas.GoalTransfer, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    goal_service.transfer_goal(db, goal_id, transfer)
    return {"status": "transferred"}

@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    try:
        # 1. Pobieramy cel, żeby sprawdzić czy istnieje
        goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
        if not goal:
            raise HTTPException(status_code=404, detail="Cel nie istnieje")

        # 2. Usuwamy powiązane wpłaty (GoalContribution) - to rozwiązuje błąd bazy
        db.query(models.GoalContribution).filter(models.GoalContribution.goal_id == goal_id).delete()
        
        # 3. Usuwamy sam cel
        db.delete(goal)
        
        # 4. Zatwierdzamy zmiany atomowo
        db.commit()
        
        print(f"✅ Cel ID {goal_id} usunięty. Środki zostały zwolnione na koncie ID {goal.account_id}")
        return {"status": "deleted"}
        
    except Exception as e:
        db.rollback()
        print(f"❌ BŁĄD podczas usuwania celu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd serwera: {str(e)}")

@router.get("/loans")
def get_loans(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    loans = db.query(models.Loan).order_by(models.Loan.next_payment_date).all()
    today = date.today()
    
    print(f"\n🔍 ===== GET /api/loans wywołane, dziś: {today} =====")
    
    # Kategorie alertów
    overdue = []      # Przeterminowane (< today)
    urgent = []       # Pilne (0-7 dni)
    upcoming = []     # Zbliżające się (8-30 dni)
    all_loans = []
    
    total_overdue = 0.0
    total_urgent = 0.0
    total_upcoming = 0.0
    
    for l in loans:
        # Dodaj do listy wszystkich
        all_loans.append({
            "id": l.id,
            "name": l.name,
            "total": float(l.total_amount),
            "remaining": float(l.remaining_amount),
            "monthly": float(l.monthly_payment),
            "next_date": str(l.next_payment_date)
        })
        
        # Jeśli kredyt spłacony - pomiń alerty
        if l.remaining_amount <= 0:
            print(f"   ⏭️ {l.name}: spłacony (remaining=0)")
            continue
        
        print(f"\n   📋 Sprawdzam kredyt: {l.name} (ID: {l.id})")
        print(f"      Next payment: {l.next_payment_date}")
        
       # Sprawdź czy płatność już jest planowana (w przyszłości, bez ograniczenia do cyklu)
        print(f"      Szukam planowanej transakcji dla loan_id={l.id}")

        existing_planned = db.query(models.Transaction).filter(
            models.Transaction.loan_id == l.id,
            models.Transaction.status == 'planowana',
            models.Transaction.date >= today  # Tylko przyszłe/dzisiejsze
        ).first()
        
        print(f"      Szukam planowanej transakcji dla loan_id={l.id}, status='planowana'")
        print(f"      Znaleziono: {existing_planned is not None}")
        
        if existing_planned:
            print(f"      ✅ Jest planowana: '{existing_planned.description}' (data: {existing_planned.date})")
            print(f"      ⏭️ POMIJAM ALERT")
            continue
        else:
            print(f"      ⚠️ BRAK planowanej - DODAM DO ALERTÓW")
        
        # Oblicz dni do płatności
        days_until = (l.next_payment_date - today).days
        print(f"      Dni do płatności: {days_until}")
        
        payment_info = {
            "loan_id": l.id,
            "name": l.name,
            "amount": float(l.monthly_payment),
            "date": str(l.next_payment_date),
            "days_until": days_until
        }
        
        # Kategoryzuj według pilności
        if days_until < 0:
            print(f"      🔴 OVERDUE (przeterminowane)")
            overdue.append(payment_info)
            total_overdue += float(l.monthly_payment)
        elif days_until <= 7:
            print(f"      🟡 URGENT (pilne 0-7 dni)")
            urgent.append(payment_info)
            total_urgent += float(l.monthly_payment)
        elif days_until <= 30:
            print(f"      🔵 UPCOMING (zbliżające się 8-30 dni)")
            upcoming.append(payment_info)
            total_upcoming += float(l.monthly_payment)
        else:
            print(f"      ⏭️ Za daleko ({days_until} dni) - pomijam")
    
    print(f"\n📊 Podsumowanie alertów:")
    print(f"   Overdue: {len(overdue)} ({total_overdue} zł)")
    print(f"   Urgent: {len(urgent)} ({total_urgent} zł)")
    print(f"   Upcoming: {len(upcoming)} ({total_upcoming} zł)")
    print(f"   has_alerts: {len(overdue) > 0 or len(urgent) > 0 or len(upcoming) > 0}")
    print(f"===== KONIEC GET /api/loans =====\n")
    
    return {
        "loans": all_loans,
        "alerts": {
            "overdue": overdue,
            "urgent": urgent,
            "upcoming": upcoming,
            "total_overdue": total_overdue,
            "total_urgent": total_urgent,
            "total_upcoming": total_upcoming,
            "has_alerts": len(overdue) > 0 or len(urgent) > 0 or len(upcoming) > 0
        }
    }
    
@router.post("/loans")
def create_loan(loan: schemas.LoanCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db_loan = models.Loan(**loan.dict()); db.add(db_loan); db.commit(); return {"status": "ok"}
@router.put("/loans/{loan_id}")
def update_loan(loan_id: int, loan: schemas.LoanUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db_loan = db.query(models.Loan).filter(models.Loan.id == loan_id).first()
    if not db_loan: raise HTTPException(status_code=404)
    db_loan.name = loan.name; db_loan.total_amount = loan.total_amount; db_loan.remaining_amount = loan.remaining_amount; db_loan.monthly_payment = loan.monthly_payment; db_loan.next_payment_date = loan.next_payment_date; db.commit(); return {"status": "updated"}

# --- KATEGORIE (POPRAWIONE) ---
@router.get("/categories")
def get_categories(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    return db.query(models.Category).order_by(models.Category.name).all()

@router.post("/categories")
def create_category(cat: schemas.CategoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    if db.query(models.Category).filter(models.Category.name == cat.name).first(): raise HTTPException(status_code=400, detail="Kategoria istnieje")
    # Mapujemy 'icon' z JSONa na 'icon_name' w bazie
    db.add(models.Category(name=cat.name, monthly_limit=cat.monthly_limit, icon_name=cat.icon, color=cat.color));
    db.commit();
    return {"status": "ok"}

@router.put("/categories/{cat_id}")
def update_category(cat_id: int, cat: schemas.CategoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db_cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    db_cat.name = cat.name; db_cat.monthly_limit = cat.monthly_limit;
    # Mapujemy 'icon' z JSONa na 'icon_name' w bazie
    if cat.icon: db_cat.icon_name = cat.icon
    if cat.color: db_cat.color = cat.color
    db.commit(); return {"status": "updated"}

@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db.query(models.Category).filter(models.Category.id == cat_id).delete(); db.commit(); return {"status": "deleted"}

# --- POZOSTAŁE ---
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

# --- TREND KATEGORII ---
@router.get("/categories/{cat_id}/trend")
def get_category_trend(cat_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    """Zwraca trend wydatków dla kategorii (ostatnie 6 miesięcy)"""
    
    category = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategoria nie istnieje")
    
    data = []
    total_sum = 0.0
    months_with_data = 0
    
    # Ostatnie 6 okresów rozliczeniowych
    for i in range(5, -1, -1):
        offset = -i  # -5, -4, -3, -2, -1, 0
        start, end = utils.get_billing_period(db, offset)
        
        # Suma wydatków w tej kategorii w tym okresie
        raw_sum = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.category_id == cat_id,
            models.Transaction.type == 'expense',
            models.Transaction.status == 'zrealizowana',
            models.Transaction.date >= start,
            models.Transaction.date <= end
        ).scalar()
        
        amount = float(raw_sum) if raw_sum is not None else 0.0
        
        if amount > 0:
            total_sum += amount
            months_with_data += 1
        
        # Label miesiąca
        months = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"]
        label = f"{months[start.month - 1]}"
        
        data.append({
            "label": label,
            "amount": amount,
            "period_start": str(start),
            "period_end": str(end)
        })
    
    # Oblicz średnią (tylko miesiące z danymi)
    average = total_sum / months_with_data if months_with_data > 0 else 0.0
    
    # Sugestia limitu (średnia + 10% bufor)
    suggested_limit = average * 1.1 if average > 0 else 0.0
    
    return {
        "category_name": category.name,
        "trend": data,
        "average": average,
        "suggested_limit": suggested_limit,
        "current_limit": float(category.monthly_limit)
    }
