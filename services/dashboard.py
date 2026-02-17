from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import models, utils
from datetime import date

def get_dashboard_data(db: Session, offset: int):
    start_date, end_date = utils.get_billing_period(db, offset)
    
    def get_sum(query_filter):
        result = db.query(func.sum(models.Transaction.amount)).filter(query_filter).scalar()
        return float(result) if result is not None else 0.0

    # 1. Salda
    raw_total = db.query(func.sum(models.Account.balance)).scalar()
    total_balance = float(raw_total) if raw_total is not None else 0.0
    
    raw_ror = db.query(func.sum(models.Account.balance)).filter(models.Account.is_savings == False).scalar()
    disposable_balance = float(raw_ror) if raw_ror is not None else 0.0

    raw_debt = db.query(func.sum(models.Loan.remaining_amount)).scalar()
    total_debt = float(raw_debt) if raw_debt is not None else 0.0
    
    # 2. Przychody i Wydatki (Realizowane i Planowane)
    inc_realized = get_sum((models.Transaction.type == 'income') & (models.Transaction.status == 'zrealizowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    inc_planned = get_sum((models.Transaction.type == 'income') & (models.Transaction.status == 'planowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    
    exp_realized = get_sum((models.Transaction.type == 'expense') & (models.Transaction.status == 'zrealizowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))
    exp_planned = get_sum((models.Transaction.type == 'expense') & (models.Transaction.status == 'planowana') & (models.Transaction.date >= start_date) & (models.Transaction.date <= end_date))

    # 3. Prognoza ROR
    forecast_ror = disposable_balance + inc_planned - exp_planned

    # 4. Transfery na oszczędności (do wskaźnika oszczędności)
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

    savings_rate = 0.0
    if inc_realized > 0:
        savings_rate = ((inc_realized - exp_realized) / inc_realized) * 100

    # 5. Cele - obliczanie monthly_need
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
            
            contribs = db.query(func.sum(models.GoalContribution.amount)).filter(
                models.GoalContribution.goal_id == g.id,
                models.GoalContribution.date >= start_date,
                models.GoalContribution.date <= end_date
            ).scalar()
            paid_this_cycle = float(contribs) if contribs else 0.0
            
            virtual_start_amount = current - paid_this_cycle
            total_missing_at_start = target - virtual_start_amount
            rate_per_cycle = total_missing_at_start / cycles_left
            actual_need = rate_per_cycle - paid_this_cycle
            
            if actual_need < 0: actual_need = 0
            goals_monthly_need += actual_need

    # 6. Ostatnie transakcje
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

def get_trend_data(db: Session):
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
