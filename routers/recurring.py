from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import date
import database, models, schemas, utils
from sqlalchemy import func

router = APIRouter(prefix="/api/recurring", tags=["Recurring"])

@router.get("")
def get_recurring(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    return db.query(models.RecurringTransaction).options(joinedload(models.RecurringTransaction.category)).all()

@router.post("")
def create_recurring(rec: schemas.RecurringCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    cat = db.query(models.Category).filter(
    func.lower(models.Category.name) == rec.category_name.lower().strip()
    ).first()
    if not cat:
        cat = models.Category(
        name=rec.category_name,
        icon_name='tag',
        color='#94a3b8'
        )
        db.add(cat); db.commit()
    
    new_rec = models.RecurringTransaction(
        name=rec.name, amount=rec.amount, day_of_month=rec.day_of_month,
        category_id=cat.id, account_id=rec.account_id
    )
    db.add(new_rec); db.commit()
    return {"status": "created"}

@router.delete("/{id}")
def delete_recurring(id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id).delete()
    db.commit()
    return {"status": "deleted"}

@router.get("/check")
def check_due_payments(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    """Sprawdza płatności wymagalne W OBECNYM CYKLU ROZLICZENIOWYM."""
    import calendar
    
    today = date.today()
    start_date, end_date = utils.get_billing_period(db, 0)
    
    all_recs = db.query(models.RecurringTransaction).filter(
        models.RecurringTransaction.is_active == True
    ).all()
    
    due = []
    
    for r in all_recs:
        try:
            payment_date = date(today.year, today.month, r.day_of_month)
        except ValueError:
            last_day = calendar.monthrange(today.year, today.month)[1]
            payment_date = date(today.year, today.month, last_day)
        
        if not (start_date <= payment_date <= end_date):
            continue
        
        if payment_date > today:
            continue
        
        if r.last_run_date and r.last_run_date >= start_date:
            continue
        
        due.append({
            "id": r.id,
            "name": r.name,
            "amount": float(r.amount),
            "category": r.category.name if r.category else "Inne",
            "account_id": r.account_id,
            "payment_date": str(payment_date)
        })
    
    return due

@router.post("/{id}/process")
def process_recurring(id: int, data: schemas.RecurringExecute, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    rec = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id).first()
    if not rec: raise HTTPException(status_code=404)
    
    # 1. Dodaj transakcję jako PLANOWANĄ
    tx = models.Transaction(
        description=rec.name,
        amount=rec.amount,
        date=data.date,
        type="expense",
        account_id=rec.account_id,
        category_id=rec.category_id,
        status="planowana"
    )
    db.add(tx)
    
    # 2. Zaktualizuj datę ostatniego wykonania
    rec.last_run_date = data.date
    db.commit()
    return {"status": "processed"}

# NOWE: Endpoint do pomijania płatności w tym miesiącu
@router.post("/{id}/skip")
def skip_recurring(id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    rec = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id).first()
    if not rec: raise HTTPException(status_code=404)
    
    # Tylko aktualizujemy datę, nie tworzymy transakcji
    rec.last_run_date = date.today()
    db.commit()
    return {"status": "skipped"}
