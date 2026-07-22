from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import models, utils
from datetime import date

def get_dashboard_data(db: Session, offset: int, user_id: int):
    start_date, end_date = utils.get_billing_period(db, offset, user_id=user_id)

    def get_sum(query_filter):
        result = db.query(func.sum(models.Transaction.amount)).filter(query_filter).scalar()
        return float(result) if result is not None else 0.0

    # 1. Salda - tylko konta usera
    raw_total = db.query(func.sum(models.Account.balance)).filter(
        models.Account.user_id == user_id
    ).scalar()
    total_balance = float(raw_total) if raw_total is not None else 0.0

    raw_ror = db.query(func.sum(models.Account.balance)).filter(
        models.Account.user_id == user_id,
        models.Account.is_savings == False
    ).scalar()
    disposable_balance = float(raw_ror) if raw_ror is not None else 0.0

    # Obniż "dostępne środki" o zablokowane środki (blokady kartowe/autoryzacje).
    # NIE jest to sprzężenie z ING podczas importu — używamy salda policzonego
    # z transakcji w apce i odejmujemy zapisany snapshot blocked_funds
    # (liczony przy imporcie: max(0, ITBD + limit_debetu − ITAV)).
    raw_blocked = db.query(func.sum(models.Account.blocked_funds)).filter(
        models.Account.user_id == user_id,
        models.Account.is_savings == False
    ).scalar()
    blocked_total = float(raw_blocked) if raw_blocked is not None else 0.0
    disposable_balance -= blocked_total

    raw_debt = db.query(func.sum(models.Loan.remaining_amount)).filter(
        models.Loan.user_id == user_id
    ).scalar()
    total_debt = float(raw_debt) if raw_debt is not None else 0.0

    # 2. Konta ROR usera
    ror_account_ids = [
        acc.id for acc in db.query(models.Account).filter(
            models.Account.user_id == user_id,
            models.Account.is_savings == False
        ).all()
    ]

    # Wszystkie konta usera
    all_account_ids = [
        acc.id for acc in db.query(models.Account).filter(
            models.Account.user_id == user_id
        ).all()
    ]

    # 3. Przychody i wydatki
    inc_realized = get_sum(
        (models.Transaction.type == 'income') &
        (models.Transaction.status == 'zrealizowana') &
        (models.Transaction.date >= start_date) &
        (models.Transaction.date <= end_date) &
        (models.Transaction.account_id.in_(all_account_ids))
    )
    exp_realized = get_sum(
        (models.Transaction.type == 'expense') &
        (models.Transaction.status == 'zrealizowana') &
        (models.Transaction.date >= start_date) &
        (models.Transaction.date <= end_date) &
        (models.Transaction.account_id.in_(all_account_ids))
    )
    inc_planned = get_sum(
        (models.Transaction.type == 'income') &
        (models.Transaction.status == 'planowana') &
        (models.Transaction.date >= start_date) &
        (models.Transaction.date <= end_date) &
        (models.Transaction.account_id.in_(ror_account_ids))
    )
    exp_planned = get_sum(
        (models.Transaction.type == 'expense') &
        (models.Transaction.status == 'planowana') &
        (models.Transaction.date >= start_date) &
        (models.Transaction.date <= end_date) &
        (models.Transaction.account_id.in_(ror_account_ids))
    )
    inc_planned_all = get_sum(
        (models.Transaction.type == 'income') &
        (models.Transaction.status == 'planowana') &
        (models.Transaction.date >= start_date) &
        (models.Transaction.date <= end_date) &
        (models.Transaction.account_id.in_(all_account_ids))
    )
    exp_planned_all = get_sum(
        (models.Transaction.type == 'expense') &
        (models.Transaction.status == 'planowana') &
        (models.Transaction.date >= start_date) &
        (models.Transaction.date <= end_date) &
        (models.Transaction.account_id.in_(all_account_ids))
    )

    # 4. Planowane transfery
    planned_transfers = db.query(models.Transaction).filter(
        models.Transaction.type == 'transfer',
        models.Transaction.status == 'planowana',
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
        models.Transaction.account_id.in_(all_account_ids)
    ).all()

    planned_transfers_out = 0.0
    planned_transfers_in = 0.0
    for t in planned_transfers:
        source = db.query(models.Account).filter(
            models.Account.id == t.account_id,
            models.Account.user_id == user_id
        ).first()
        target = db.query(models.Account).filter(
            models.Account.id == t.target_account_id,
            models.Account.user_id == user_id
        ).first()
        if source and target:
            if not source.is_savings and target.is_savings:
                planned_transfers_out += float(t.amount)
            elif source.is_savings and not target.is_savings:
                planned_transfers_in += float(t.amount)

    # 5. Prognoza ROR
    forecast_ror = disposable_balance + inc_planned - exp_planned - planned_transfers_out + planned_transfers_in

    # 6. Transfery na oszczędności
    period_transfers = db.query(models.Transaction).options(
        joinedload(models.Transaction.account),
        joinedload(models.Transaction.target_account)
    ).filter(
        models.Transaction.type == 'transfer',
        models.Transaction.status == 'zrealizowana',
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
        models.Transaction.account_id.in_(all_account_ids)
    ).all()

    savings_realized = 0.0
    for t in period_transfers:
        if t.account and not t.account.is_savings and t.target_account and t.target_account.is_savings:
            savings_realized += float(t.amount)

    savings_rate = 0.0
    if inc_realized > 0:
        savings_rate = ((inc_realized - exp_realized) / inc_realized) * 100

    # 7. Cele
    goals = db.query(models.Goal).filter(
        models.Goal.is_archived == False,
        models.Goal.user_id == user_id
    ).all()
    goals_monthly_need = 0.0
    goals_total_saved = 0.0

    for g in goals:
        current = float(g.current_amount)
        target = float(g.target_amount)
        goals_total_saved += current
        if offset < 0:
            continue
        remaining = target - current
        if remaining > 0:
            cycles_left = 1
            check_offset = offset
            while True:
                _, cycle_end = utils.get_billing_period(db, check_offset, user_id=user_id)
                if cycle_end >= g.deadline:
                    break
                cycles_left += 1
                check_offset += 1
                if cycles_left > 120:
                    break
            contribs = db.query(func.sum(models.GoalContribution.amount)).filter(
                models.GoalContribution.goal_id == g.id,
                models.GoalContribution.date >= start_date,
                models.GoalContribution.date <= end_date
            ).scalar()
            paid_this_cycle = float(contribs) if contribs else 0.0
            virtual_start_amount = current - paid_this_cycle
            total_missing_at_start = target - virtual_start_amount
            rate_per_cycle = total_missing_at_start / cycles_left if cycles_left > 0 else 0
            actual_need = rate_per_cycle - paid_this_cycle
            if actual_need < 0:
                actual_need = 0
            goals_monthly_need += actual_need

    if offset < 0:
        goals_monthly_need = None

    # 8. Ostatnie transakcje
    recent = db.query(models.Transaction).options(
        joinedload(models.Transaction.category),
        joinedload(models.Transaction.loan)
    ).filter(
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
        models.Transaction.account_id.in_(all_account_ids)
    ).order_by(
        models.Transaction.date.desc(),
        models.Transaction.id.desc()
    ).all()

    tx_list = []
    for t in recent:
        cat_name = t.category.name if t.category else "-"
        if t.type == 'transfer':
            cat_name = "Transfer"
        tx_list.append({
            "id": t.id, "desc": t.description, "amount": float(t.amount),
            "type": t.type, "category": cat_name, "date": str(t.date),
            "account_id": t.account_id, "target_account_id": t.target_account_id,
            "category_name": cat_name, "status": t.status, "loan_id": t.loan_id
        })

    return {
        "total_balance": total_balance,
        "disposable_balance": disposable_balance,
        "forecast_ror": forecast_ror,
        "savings_realized": savings_realized,
        "savings_rate": savings_rate,
        "total_debt": total_debt,
        "monthly_income_realized": inc_realized,
        "monthly_income_forecast": inc_realized + inc_planned_all,
        "monthly_expenses_realized": exp_realized,
        "monthly_expenses_forecast": exp_realized + exp_planned_all,
        "goals_monthly_need": goals_monthly_need,
        "goals_total_saved": goals_total_saved,
        "recent_transactions": tx_list,
        "period_start": str(start_date),
        "period_end": str(end_date)
    }


def get_trend_data(db: Session, user_id: int):
    # Pobierz konta usera
    all_account_ids = [
        acc.id for acc in db.query(models.Account).filter(
            models.Account.user_id == user_id
        ).all()
    ]

    data = []
    for i in range(5, -1, -1):
        offset = -i
        start, end = utils.get_billing_period(db, offset, user_id=user_id)
        raw_inc = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.type == 'income',
            models.Transaction.status == 'zrealizowana',
            models.Transaction.date >= start,
            models.Transaction.date <= end,
            models.Transaction.account_id.in_(all_account_ids)
        ).scalar()
        raw_exp = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.type == 'expense',
            models.Transaction.status == 'zrealizowana',
            models.Transaction.date >= start,
            models.Transaction.date <= end,
            models.Transaction.account_id.in_(all_account_ids)
        ).scalar()
        inc = float(raw_inc) if raw_inc is not None else 0.0
        exp = float(raw_exp) if raw_exp is not None else 0.0
        months = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze",
                  "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"]
        data.append({
            "label": months[start.month - 1],
            "income": inc,
            "expense": exp
        })
    return data
