from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import date
import database, models, schemas, utils

router = APIRouter(prefix="/api/recurring", tags=["Recurring"])

@router.get("")
def get_recurring(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    return db.query(models.RecurringTransaction).options(joinedload(models.RecurringTransaction.category)).all()

@router.post("")
def create_recurring(rec: schemas.RecurringCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    cat = db.query(models.Category).filter(models.Category.name == rec.category_name).first()
    if not cat:
        cat = models.Category(name=rec.category_name)
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
    """Sprawdza, które płatności powinny być wykonane w tym miesiącu, a jeszcze nie były."""
    today = date.today()
    # Początek obecnego miesiąca
    start_of_month = date(today.year, today.month, 1)
    
    all_recs = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.is_active == True).all()
    due = []
    
    for r in all_recs:
        # Jeśli jeszcze nie było uruchamiane LUB ostatnie uruchomienie było przed tym miesiącem
        if not r.last_run_date or r.last_run_date < start_of_month:
            # I jeśli dzień miesiąca już minął lub jest dzisiaj
            if today.day >= r.day_of_month:
                due.append({
                    "id": r.id,
                    "name": r.name,
                    "amount": float(r.amount),
                    "category": r.category.name if r.category else "Inne",
                    "account_id": r.account_id
                })
    return due

@router.post("/{id}/process")
def process_recurring(id: int, data: schemas.RecurringExecute, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    rec = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id).first()
    if not rec: raise HTTPException(status_code=404)
    
    # 1. Dodaj transakcję
    tx = models.Transaction(
        description=rec.name, amount=rec.amount, date=data.date,
        type="expense", account_id=rec.account_id, category_id=rec.category_id,
        status="zrealizowana"
    )
    db.add(tx)
    
    # 2. Zaktualizuj saldo
    utils.update_balance(db, rec.account_id, rec.amount, "expense", None, False)
    
    # 3. Zaktualizuj datę ostatniego wykonania
    rec.last_run_date = data.date
    db.commit()
    return {"status": "processed"}
