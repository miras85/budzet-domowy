from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import date
import database, models, schemas, utils
from sqlalchemy import func

router = APIRouter(prefix="/api/recurring", tags=["Recurring"])

@router.get("")
def get_recurring(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    owner_id = database.get_data_owner_id(current_user, db)
    return db.query(models.RecurringTransaction).options(
        joinedload(models.RecurringTransaction.category)
    ).filter(
        models.RecurringTransaction.user_id == owner_id
    ).all()

@router.post("")
def create_recurring(rec: schemas.RecurringCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    owner_id = database.get_data_owner_id(current_user, db)
    cat = db.query(models.Category).filter(
        func.lower(models.Category.name) == rec.category_name.lower().strip(),
        models.Category.user_id == owner_id
    ).first()
    if not cat:
        cat = models.Category(
            name=rec.category_name,
            icon_name='tag',
            color='#94a3b8',
            user_id=owner_id
        )
        db.add(cat)
        db.commit()

    new_rec = models.RecurringTransaction(
        name=rec.name,
        amount=rec.amount,
        day_of_month=rec.day_of_month,
        category_id=cat.id,
        account_id=rec.account_id,
        user_id=owner_id
    )
    db.add(new_rec)
    db.commit()
    return {"status": "created"}

@router.put("/{id}")
def update_recurring(id: int, rec: schemas.RecurringCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    owner_id = database.get_data_owner_id(current_user, db)
    db_rec = db.query(models.RecurringTransaction).filter(
        models.RecurringTransaction.id == id,
        models.RecurringTransaction.user_id == owner_id
    ).first()
    if not db_rec:
        raise HTTPException(status_code=404)

    cat = db.query(models.Category).filter(
        func.lower(models.Category.name) == rec.category_name.lower().strip(),
        models.Category.user_id == owner_id
    ).first()
    if not cat:
        cat = models.Category(
            name=rec.category_name,
            icon_name='tag',
            color='#94a3b8',
            user_id=owner_id
        )
        db.add(cat)
        db.flush()

    db_rec.name = rec.name
    db_rec.amount = rec.amount
    db_rec.day_of_month = rec.day_of_month
    db_rec.category_id = cat.id
    db_rec.account_id = rec.account_id
    db.commit()
    return {"status": "updated"}

@router.delete("/{id}")
def delete_recurring(id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    owner_id = database.get_data_owner_id(current_user, db)
    db.query(models.RecurringTransaction).filter(
        models.RecurringTransaction.id == id,
        models.RecurringTransaction.user_id == owner_id
    ).delete()
    db.commit()
    return {"status": "deleted"}

@router.get("/check")
def check_due_payments(db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    """Sprawdza płatności wymagalne w OBECNYM CYKLU ROZLICZENIOWYM."""
    import calendar
    owner_id = database.get_data_owner_id(current_user, db)
    today = date.today()
    start_date, end_date = utils.get_billing_period(db, 0, user_id=owner_id)

    all_recs = db.query(models.RecurringTransaction).filter(
        models.RecurringTransaction.is_active == True,
        models.RecurringTransaction.user_id == owner_id
    ).all()

    due = []

    for r in all_recs:
        payday = 25

        if r.day_of_month < payday:
            base_month = start_date.month + 1
            base_year = start_date.year
            if base_month > 12:
                base_month = 1
                base_year += 1
        else:
            base_month = start_date.month
            base_year = start_date.year

        try:
            payment_date = date(base_year, base_month, r.day_of_month)
        except ValueError:
            last_day = calendar.monthrange(base_year, base_month)[1]
            payment_date = date(base_year, base_month, last_day)

        if not (start_date <= payment_date <= end_date):
            continue

        days_until = (payment_date - today).days

        if days_until > 7:
            continue
        if days_until < 0:
            continue

        if r.last_run_date and r.last_run_date >= start_date:
            continue

        due.append({
            "id": r.id,
            "name": r.name,
            "amount": float(r.amount),
            "category": r.category.name if r.category else "Inne",
            "account_id": r.account_id,
            "payment_date": str(payment_date),
            "days_until": days_until
        })

    return due

@router.post("/{id}/process")
def process_recurring(id: int, data: schemas.RecurringExecute, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    owner_id = database.get_data_owner_id(current_user, db)
    rec = db.query(models.RecurringTransaction).filter(
        models.RecurringTransaction.id == id,
        models.RecurringTransaction.user_id == owner_id
    ).first()
    if not rec:
        raise HTTPException(status_code=404)

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
    rec.last_run_date = data.date
    db.commit()
    return {"status": "processed"}

@router.post("/{id}/skip")
def skip_recurring(id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(database.get_current_user)):
    owner_id = database.get_data_owner_id(current_user, db)
    rec = db.query(models.RecurringTransaction).filter(
        models.RecurringTransaction.id == id,
        models.RecurringTransaction.user_id == owner_id
    ).first()
    if not rec:
        raise HTTPException(status_code=404)

    rec.last_run_date = date.today()
    db.commit()
    return {"status": "skipped"}
