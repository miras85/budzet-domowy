from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import date, timedelta
import database, models, schemas, utils

router = APIRouter(prefix="/api", tags=["Finance"])

# --- DASHBOARD ---
@router.get("/dashboard")
def get_dashboard(offset: int = 0, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    start_date, end_date = utils.get_billing_period(db, offset)
    
    def get_sum(query_filter):
        result = db.query(func.sum(models.Transaction.amount)).filter(query_filter).scalar()
        return float(result) if result is not None else 0.0

    # 1. Całkowite saldo wszystkich kont
    raw_total = db.query(func.sum(models.Account.balance)).scalar()
    total_balance = float(raw_total) if raw_total is not None else 0.0
    
    # 2. Saldo ROR (Dostępne środki na życie)
    raw_ror = db.query(func.sum(models.Account.balance)).filter(models.Account.is_savings == False).scalar()
    disposable_balance = float(raw_ror) if raw_ror is not None else 0.0

    # Całkowity dług
    raw_debt = db.query(func.sum(models.Loan.remaining_amount)).scalar()
    total_debt = float(raw_debt) if raw_debt is not None else 0.0
    
    # Przychody i Wydatki
    inc_realized = get_sum((models.Transaction.type == 'income') & (models.Transaction.status == 'zrealizowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    inc_planned = get_sum((models.Transaction.type == 'income') & (models.Transaction.status == 'planowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    
    exp_realized = get_sum((models.Transaction.type == 'expense') & (models.Transaction.status == 'zrealizowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    exp_planned = get_sum((models.Transaction.type == 'expense') & (models.Transaction.status == 'planowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))

    # Prognoza ROR
    forecast_ror = disposable_balance + inc_planned - exp_planned

    # Transfery na oszczędności
    period_transfers = db.query(models.Transaction).options(joinedload(models.Transaction.account), joinedload(models.Transaction.target_account)).filter(
        models.Transaction.type == 'transfer',
        models.Transaction.status == 'zrealizowana',
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date
    ).all()
    
    savings_realized = 0.0
    for t in period_transfers:
        if t.account and not t.account.is_savings and t.target_account and t.target_account.is_savings:
            savings_realized += float(t.amount)

    # Wskaźnik oszczędności
    savings_rate = 0.0
    if inc_realized > 0:
        savings_rate = ((inc_realized - exp_realized) / inc_realized) * 100

    # Cele (proste podsumowanie do dashboardu)
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
                _, cycle_end = utils.get_billing_period(db, check_offset)
                if cycle_end >= g.deadline: break
                cycles_left += 1
                check_offset += 1
                if cycles_left > 120: break
            
            # Sumujemy GoalContribution w tym cyklu
            contribs = db.query(func.sum(models.GoalContribution.amount)).filter(
                models.GoalContribution.goal_id == g.id,
                models.GoalContribution.date >= start_date,
                models.GoalContribution.date <= end_date
            ).scalar()
            paid_this_cycle = float(contribs) if contribs else 0.0
            
            # MATEMATYKA:
            virtual_start_amount = current - paid_this_cycle
            total_missing_at_start = target - virtual_start_amount
            rate_per_cycle = total_missing_at_start / cycles_left
            actual_need = rate_per_cycle - paid_this_cycle
            
            if actual_need < 0: actual_need = 0
            goals_monthly_need += actual_need

    recent = db.query(models.Transaction).options(joinedload(models.Transaction.category), joinedload(models.Transaction.loan)).filter(models.Transaction.date >= start_date, models.Transaction.date <= end_date).order_by(models.Transaction.date.desc(), models.Transaction.id.desc()).all()
    
    tx_list = []
    for t in recent:
        cat_name = t.category.name if t.category else "-"
        if t.type == 'transfer': cat_name = "Transfer"
        
        tx_list.append({
            "id": t.id, "desc": t.description, "amount": float(t.amount),
            "type": t.type, "category": cat_name, "date": str(t.date),
            "account_id": t.account_id, "target_account_id": t.target_account_id,
            "category_name": cat_name, "status": t.status,
            "loan_id": t.loan_id
        })

    return {
        "total_balance": total_balance,
        "disposable_balance": disposable_balance,
        "forecast_ror": forecast_ror,
        "savings_realized": savings_realized,
        "savings_rate": savings_rate,
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

@router.get("/stats/trend")
def get_trend(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    data = []
    for i in range(5, -1, -1):
        offset = -i
        start, end = utils.get_billing_period(db, offset)
        raw_inc = db.query(func.sum(models.Transaction.amount)).filter(models.Transaction.type == 'income', models.Transaction.status == 'zrealizowana', models.Transaction.date >= start, models.Transaction.date <= end).scalar()
        raw_exp = db.query(func.sum(models.Transaction.amount)).filter(models.Transaction.type == 'expense', models.Transaction.status == 'zrealizowana', models.Transaction.date >= start, models.Transaction.date <= end).scalar()
        inc = float(raw_inc) if raw_inc is not None else 0.0
        exp = float(raw_exp) if raw_exp is not None else 0.0
        months = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"]
        label = f"{months[start.month - 1]}"
        data.append({"label": label, "income": inc, "expense": exp})
    return data

# --- TRANSAKCJE ---
@router.post("/transactions")
def add_transaction(tx: schemas.TransactionCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    cat_id = None
    
    if tx.loan_id:
        target_cat = "Spłata zobowiązań"
        cat = db.query(models.Category).filter(models.Category.name == target_cat).first()
        if not cat:
            cat = models.Category(name=target_cat)
            db.add(cat)
            db.commit()
        cat_id = cat.id
    elif tx.type != 'transfer' and tx.category_name:
        cat = db.query(models.Category).filter(models.Category.name == tx.category_name).first()
        if not cat:
            cat = models.Category(name=tx.category_name)
            db.add(cat); db.commit()
        cat_id = cat.id

    new_tx = models.Transaction(amount=tx.amount, description=tx.description, date=tx.date, type=tx.type, account_id=tx.account_id, category_id=cat_id, status=tx.status, target_account_id=tx.target_account_id, loan_id=tx.loan_id)
    db.add(new_tx)
    if tx.status == 'zrealizowana':
        utils.update_balance(db, tx.account_id, tx.amount, tx.type, tx.target_account_id, is_reversal=False)
        if tx.loan_id and tx.type == 'expense': utils.update_loan_balance(db, tx.loan_id, tx.amount, is_reversal=False)
    db.commit()
    return {"status": "added"}

@router.put("/transactions/{tx_id}")
def update_transaction(tx_id: int, tx_data: schemas.TransactionCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    old_tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not old_tx: raise HTTPException(status_code=404)
    if old_tx.status == 'zrealizowana':
        utils.update_balance(db, old_tx.account_id, old_tx.amount, old_tx.type, old_tx.target_account_id, is_reversal=True)
        if old_tx.loan_id and old_tx.type == 'expense': utils.update_loan_balance(db, old_tx.loan_id, old_tx.amount, is_reversal=True)
    
    cat_id = None
    if tx_data.loan_id:
        target_cat = "Spłata zobowiązań"
        cat = db.query(models.Category).filter(models.Category.name == target_cat).first()
        if not cat:
            cat = models.Category(name=target_cat)
            db.add(cat)
            db.commit()
        cat_id = cat.id
    elif tx_data.type != 'transfer' and tx_data.category_name:
        cat = db.query(models.Category).filter(models.Category.name == tx_data.category_name).first()
        if not cat:
            cat = models.Category(name=tx_data.category_name)
            db.add(cat); db.commit()
        cat_id = cat.id

    old_tx.amount = tx_data.amount; old_tx.description = tx_data.description; old_tx.date = tx_data.date
    old_tx.type = tx_data.type; old_tx.account_id = tx_data.account_id; old_tx.target_account_id = tx_data.target_account_id
    old_tx.category_id = cat_id; old_tx.status = tx_data.status; old_tx.loan_id = tx_data.loan_id
    
    if tx_data.status == 'zrealizowana':
        utils.update_balance(db, tx_data.account_id, tx_data.amount, tx_data.type, tx_data.target_account_id, is_reversal=False)
        if tx_data.loan_id and tx_data.type == 'expense': utils.update_loan_balance(db, tx_data.loan_id, tx_data.amount, is_reversal=False)
    db.commit()
    return {"status": "updated"}

@router.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not tx: raise HTTPException(status_code=404)
    if tx.status == 'zrealizowana':
        utils.update_balance(db, tx.account_id, tx.amount, tx.type, tx.target_account_id, is_reversal=True)
        if tx.loan_id and tx.type == 'expense': utils.update_loan_balance(db, tx.loan_id, tx.amount, is_reversal=True)
    db.delete(tx); db.commit(); return {"status": "deleted"}

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
            
            # NOWA LOGIKA: Sumujemy GoalContribution w tym cyklu
            contribs = db.query(func.sum(models.GoalContribution.amount)).filter(
                models.GoalContribution.goal_id == g.id,
                models.GoalContribution.date >= start_date,
                models.GoalContribution.date <= end_date
            ).scalar()
            paid_this_cycle = float(contribs) if contribs else 0.0
            
            # 1. Stan na początek cyklu (wirtualny)
            virtual_start_amount = float(g.current_amount) - paid_this_cycle
            
            # 2. Ile brakowało na początku cyklu do pełnej kwoty
            total_missing_at_start = float(g.target_amount) - virtual_start_amount
            
            # 3. Rata na ten cykl (Brakujące / Liczba cykli)
            rate_per_cycle = total_missing_at_start / cycles_left
            
            # 4. Ile trzeba dopłacić (Rata - Już wpłacone)
            actual_need = rate_per_cycle - paid_this_cycle
            
            if actual_need < 0:
                actual_need = 0.0
                
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
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal: raise HTTPException(status_code=404)
    source_acc = db.query(models.Account).filter(models.Account.id == fund.source_account_id).first()
    if not source_acc: raise HTTPException(status_code=404, detail="Brak konta źródłowego")
    
    # Walidacja dostępnych środków (jeśli źródło to konto oszczędnościowe)
    if source_acc.is_savings:
        reserved = db.query(func.sum(models.Goal.current_amount)).filter(models.Goal.account_id == source_acc.id).scalar()
        reserved_amount = float(reserved) if reserved else 0.0
        available = float(source_acc.balance) - reserved_amount
        
        if fund.amount > available:
            raise HTTPException(status_code=400, detail=f"Brak wolnych środków. Dostępne: {available:.2f} zł")

    # Jeśli źródło to ROR, a cel to Oszczędnościowe -> Transfer
    if not source_acc.is_savings:
        if not fund.target_savings_id: raise HTTPException(status_code=400, detail="Wymagane wskazanie konta oszczędnościowego")
        target_acc = db.query(models.Account).filter(models.Account.id == fund.target_savings_id).first()
        if not target_acc or not target_acc.is_savings: raise HTTPException(status_code=400, detail="Konto docelowe musi być oszczędnościowe")
        
        transfer_tx = models.Transaction(amount=fund.amount, description=f"Zasilenie celu: {goal.name}", date=date.today(), type="transfer", account_id=source_acc.id, target_account_id=target_acc.id, status="zrealizowana")
        db.add(transfer_tx)
        utils.update_balance(db, source_acc.id, fund.amount, "transfer", target_acc.id, is_reversal=False)
    
    # ZAPISUJEMY WPŁATĘ W NOWEJ TABELI
    contribution = models.GoalContribution(
        goal_id=goal.id,
        amount=fund.amount,
        date=date.today()
    )
    db.add(contribution)
    
    goal.current_amount = float(goal.current_amount) + fund.amount; db.commit(); return {"status": "funded"}

@router.post("/goals/{goal_id}/transfer")
def transfer_goal_funds(goal_id: int, transfer: schemas.GoalTransfer, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    source = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    target = db.query(models.Goal).filter(models.Goal.id == transfer.target_goal_id).first()
    if not source or not target: raise HTTPException(status_code=404)
    if float(source.current_amount) < transfer.amount: raise HTTPException(status_code=400, detail="Brak środków")
    
    # Aktualizacja sald celów
    source.current_amount = float(source.current_amount) - transfer.amount
    target.current_amount = float(target.current_amount) + transfer.amount
    
    # Rejestracja przesunięcia w historii (ujemna dla źródła, dodatnia dla celu)
    db.add(models.GoalContribution(goal_id=source.id, amount=-transfer.amount, date=date.today()))
    db.add(models.GoalContribution(goal_id=target.id, amount=transfer.amount, date=date.today()))
    
    db.commit(); return {"status": "transferred"}


@router.post("/goals/{goal_id}/withdraw")
def withdraw_goal_funds(goal_id: int, withdraw: schemas.GoalWithdraw, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal: raise HTTPException(status_code=404)
    
    if float(goal.current_amount) < withdraw.amount:
        raise HTTPException(status_code=400, detail="Brak wystarczających środków na celu")
    
    target_acc = db.query(models.Account).filter(models.Account.id == withdraw.target_account_id).first()
    if not target_acc: raise HTTPException(status_code=404, detail="Konto docelowe nie istnieje")

    # 1. Aktualizacja celu
    goal.current_amount = float(goal.current_amount) - withdraw.amount
    
    # 2. Rejestracja w historii celu (ujemna kwota)
    db.add(models.GoalContribution(goal_id=goal.id, amount=-withdraw.amount, date=date.today()))
    
    # 3. Logika transferu pieniędzy
    # Jeśli wypłacamy na INNE konto (np. z Oszczędnościowego na ROR), musimy zrobić transfer
    if goal.account_id != target_acc.id:
        source_acc = db.query(models.Account).filter(models.Account.id == goal.account_id).first()
        
        # Tworzymy transakcję transferu
        tx = models.Transaction(
            amount=withdraw.amount,
            description=f"Wypłata z celu: {goal.name}",
            date=date.today(),
            type="transfer",
            account_id=source_acc.id,
            target_account_id=target_acc.id,
            status="zrealizowana"
        )
        db.add(tx)
        
        # Aktualizujemy salda fizyczne kont
        utils.update_balance(db, source_acc.id, withdraw.amount, "transfer", target_acc.id, is_reversal=False)
    
    # Jeśli wypłacamy na TO SAMO konto (po prostu uwalniamy środki z celu),
    # fizyczne saldo konta się nie zmienia, zmienia się tylko "dostępne" (bo cel maleje).
    # Nie robimy nic więcej.

    db.commit()
    return {"status": "withdrawn"}


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db.query(models.Goal).filter(models.Goal.id == goal_id).delete(); db.commit(); return {"status": "deleted"}

# --- POZOSTAŁE (Kredyty, Kategorie, Konta) ---
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
    if db.query(models.Category).filter(models.Category.name == cat.name).first():
        raise HTTPException(status_code=400, detail="Kategoria istnieje")
    db.add(models.Category(name=cat.name, monthly_limit=cat.monthly_limit))
    db.commit()
    return {"status": "ok"}

@router.put("/categories/{cat_id}")
def update_category(cat_id: int, cat: schemas.CategoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db_cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    db_cat.name = cat.name
    db_cat.monthly_limit = cat.monthly_limit
    db.commit()
    return {"status": "updated"}
    
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

# NOWE: Zwracanie dostępnego salda (po odjęciu celów)
@router.get("/accounts")
def get_accounts(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    accounts = db.query(models.Account).all()
    result = []
    for acc in accounts:
        reserved = 0.0
        if acc.is_savings:
            res_val = db.query(func.sum(models.Goal.current_amount)).filter(models.Goal.account_id == acc.id).scalar()
            reserved = float(res_val) if res_val else 0.0
        
        result.append({
            "id": acc.id,
            "name": acc.name,
            "type": acc.type,
            "balance": float(acc.balance),
            "is_savings": acc.is_savings,
            "available": float(acc.balance) - reserved # NOWE POLE
        })
    return result

@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db.query(models.Transaction).filter(models.Transaction.account_id == account_id).delete(); db.query(models.Account).filter(models.Account.id == account_id).delete(); db.commit(); return {"status": "deleted"}
@router.post("/accounts")
def create_account(acc: schemas.AccountUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)): db_acc = models.Account(name=acc.name, type=acc.type, balance=acc.balance, is_savings=acc.is_savings); db.add(db_acc); db.commit(); return {"status": "ok"}
