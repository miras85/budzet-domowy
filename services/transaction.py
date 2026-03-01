from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from typing import Optional
from datetime import date
import models, schemas, utils
from sqlalchemy import func

def create_transaction(db: Session, tx: schemas.TransactionCreate):
    """Tworzy nową transakcję z atomową aktualizacją sald"""
    try:
        cat_id = None
        
        # Obsługa kategorii dla pożyczek
        if tx.loan_id:
            # Jeśli użytkownik nie wybrał kategorii, dajemy domyślną
            if not tx.category_name:
                tx.category_name = "Spłata zobowiązań"
            
            cat = db.query(models.Category).filter(
                func.lower(models.Category.name) == tx.category_name.lower().strip()
            ).first()
            
            if not cat:
                cat = models.Category(name=tx.category_name, icon_name='tag', color='#94a3b8')
                db.add(cat)
                db.flush()
            cat_id = cat.id
            
        # Obsługa zwykłych kategorii (jeśli nie transfer)
        elif tx.type != 'transfer' and tx.category_name:
            cat = db.query(models.Category).filter(
                func.lower(models.Category.name) == tx.category_name.lower().strip()
            ).first()
            if not cat:
                cat = models.Category(name=tx.category_name, icon_name='tag', color='#94a3b8')
                db.add(cat)
                db.flush()
            cat_id = cat.id

        new_tx = models.Transaction(
            amount=tx.amount,
            description=tx.description,
            date=tx.date,
            type=tx.type,
            account_id=tx.account_id,
            category_id=cat_id,
            status=tx.status,
            target_account_id=tx.target_account_id,
            loan_id=tx.loan_id
        )
        db.add(new_tx)
        db.flush()
        
        if tx.status == 'zrealizowana':
            utils.update_balance(db, tx.account_id, tx.amount, tx.type, tx.target_account_id, is_reversal=False)
            if tx.loan_id and tx.type == 'expense':
                utils.update_loan_balance(db, tx.loan_id, tx.amount, is_reversal=False)
        
        db.commit()
        return new_tx
        
    except Exception as e:
        db.rollback()
        print(f"❌ BŁĄD create_transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Błąd tworzenia transakcji: {str(e)}")

def update_transaction(db: Session, tx_id: int, tx_data: schemas.TransactionCreate):
    """Aktualizuje transakcję z atomową aktualizacją sald"""
    old_tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not old_tx:
        raise HTTPException(status_code=404, detail="Transakcja nie istnieje")
    
    try:
        # 1. Cofnij skutki starej transakcji
        if old_tx.status == 'zrealizowana':
            utils.update_balance(db, old_tx.account_id, old_tx.amount, old_tx.type, old_tx.target_account_id, is_reversal=True)
            if old_tx.loan_id and old_tx.type == 'expense':
                utils.update_loan_balance(db, old_tx.loan_id, old_tx.amount, is_reversal=True)
        
        # 2. Ustal nową kategorię
        cat_id = None
        if tx_data.loan_id:
            if not tx_data.category_name:
                tx_data.category_name = "Spłata zobowiązań"
                
            cat = db.query(models.Category).filter(
                func.lower(models.Category.name) == tx_data.category_name.lower().strip()
            ).first()
            
            if not cat:
                cat = models.Category(name=tx_data.category_name, icon_name='tag', color='#94a3b8')
                db.add(cat)
                db.flush()
            cat_id = cat.id
        elif tx_data.type != 'transfer' and tx_data.category_name:
            cat = db.query(models.Category).filter(
                func.lower(models.Category.name) == tx_data.category_name.lower().strip()
            ).first()
            if not cat:
                cat = models.Category(name=tx_data.category_name, icon_name='tag', color='#94a3b8')
                db.add(cat)
                db.flush()
            cat_id = cat.id

        # 3. Zaktualizuj pola transakcji
        old_tx.amount = tx_data.amount
        old_tx.description = tx_data.description
        old_tx.date = tx_data.date
        old_tx.type = tx_data.type
        old_tx.account_id = tx_data.account_id
        old_tx.target_account_id = tx_data.target_account_id
        old_tx.category_id = cat_id
        old_tx.status = tx_data.status
        old_tx.loan_id = tx_data.loan_id
        
        # 4. Zastosuj skutki nowej transakcji
        if tx_data.status == 'zrealizowana':
            utils.update_balance(db, tx_data.account_id, tx_data.amount, tx_data.type, tx_data.target_account_id, is_reversal=False)
            if tx_data.loan_id and tx_data.type == 'expense':
                utils.update_loan_balance(db, tx_data.loan_id, tx_data.amount, is_reversal=False)
        
        db.commit()
        return old_tx
        
    except Exception as e:
        db.rollback()
        print(f"❌ BŁĄD update_transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Błąd aktualizacji transakcji: {str(e)}")

def delete_transaction(db: Session, tx_id: int):
    """Usuwa transakcję z atomową aktualizacją sald"""
    
    tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transakcja nie istnieje")
    
    try:
        # Cofnij skutki transakcji (jeśli była zrealizowana)
        if tx.status == 'zrealizowana':
            utils.update_balance(db, tx.account_id, tx.amount, tx.type, tx.target_account_id, is_reversal=True)
            if tx.loan_id and tx.type == 'expense':
                utils.update_loan_balance(db, tx.loan_id, tx.amount, is_reversal=True)
        
        # Usuń transakcję
        db.delete(tx)
        
        db.commit()  # COMMIT jeśli wszystko OK
        
    except Exception as e:
        db.rollback()
        print(f"❌ BŁĄD delete_transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Błąd usuwania transakcji: {str(e)}")

def search_transactions(db: Session, q, date_from, date_to, category_id, account_id, type, min_amount, max_amount):
    query = db.query(models.Transaction).options(joinedload(models.Transaction.category)).filter(models.Transaction.status == 'zrealizowana')

    if q: query = query.filter(models.Transaction.description.ilike(f"%{q}%"))
    if date_from: query = query.filter(models.Transaction.date >= date_from)
    if date_to: query = query.filter(models.Transaction.date <= date_to)
    if category_id: query = query.filter(models.Transaction.category_id == category_id)
    if account_id: query = query.filter((models.Transaction.account_id == account_id) | (models.Transaction.target_account_id == account_id))
    if type: query = query.filter(models.Transaction.type == type)
    if min_amount is not None: query = query.filter(models.Transaction.amount >= min_amount)
    if max_amount is not None: query = query.filter(models.Transaction.amount <= max_amount)

    results = query.order_by(models.Transaction.date.desc(), models.Transaction.id.desc()).all()
    
    total_income = sum(float(t.amount) for t in results if t.type == 'income')
    total_expense = sum(float(t.amount) for t in results if t.type == 'expense')
    
    tx_list = []
    for t in results:
        cat_name = t.category.name if t.category else "-"
        if t.type == 'transfer': cat_name = "Transfer"
        tx_list.append({
            "id": t.id, "desc": t.description, "amount": float(t.amount),
            "type": t.type, "category": cat_name, "date": str(t.date),
            "account_id": t.account_id, "target_account_id": t.target_account_id
        })

    return {
        "transactions": tx_list,
        "summary": {
            "income": total_income,
            "expense": total_expense,
            "balance": total_income - total_expense,
            "count": len(tx_list)
        }
    }
