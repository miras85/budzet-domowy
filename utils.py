from sqlalchemy.orm import Session
from datetime import date, timedelta
import calendar
import models

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

# --- POMOCNICZE DO SALD ---
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

def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year,month)[1])
    return date(year, month, day)

def update_loan_balance(db, loan_id, amount, is_reversal):
    if not loan_id: return
    loan = db.query(models.Loan).filter(models.Loan.id == loan_id).first()
    if not loan: return
    
    val = float(amount)
    
    if is_reversal:
        # Cofnięcie transakcji: zwiększamy dług, cofamy datę
        loan.remaining_amount = float(loan.remaining_amount) + val
        if loan.next_payment_date:
            loan.next_payment_date = add_months(loan.next_payment_date, -1)
    else:
        # Nowa transakcja: zmniejszamy dług, przesuwamy datę do przodu
        loan.remaining_amount = float(loan.remaining_amount) - val
        if loan.next_payment_date:
            loan.next_payment_date = add_months(loan.next_payment_date, 1)
