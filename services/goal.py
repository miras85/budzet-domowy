from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from datetime import date
import models, schemas, utils

def fund_goal(db: Session, goal_id: int, fund: schemas.GoalFund):
    """Zasila cel z atomową aktualizacją sald i transferów"""
    
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Cel nie istnieje")
    
    source_acc = db.query(models.Account).filter(models.Account.id == fund.source_account_id).first()
    if not source_acc:
        raise HTTPException(status_code=404, detail="Brak konta źródłowego")
    
    try:
        # Walidacja dostępnych środków (jeśli źródło to konto oszczędnościowe)
        if source_acc.is_savings:
            reserved = db.query(func.sum(models.Goal.current_amount)).filter(models.Goal.account_id == source_acc.id).scalar()
            reserved_amount = float(reserved) if reserved else 0.0
            available = float(source_acc.balance) - reserved_amount
            if fund.amount > available:
                raise HTTPException(status_code=400, detail=f"Brak wolnych środków. Dostępne: {available:.2f} zł")

        # Jeśli źródło to ROR, a cel to Oszczędnościowe -> Transfer
        if not source_acc.is_savings:
            if not fund.target_savings_id:
                raise HTTPException(status_code=400, detail="Wymagane wskazanie konta oszczędnościowego")
            
            target_acc = db.query(models.Account).filter(models.Account.id == fund.target_savings_id).first()
            if not target_acc or not target_acc.is_savings:
                raise HTTPException(status_code=400, detail="Konto docelowe musi być oszczędnościowe")
            
            # Utwórz transakcję transferu
            transfer_tx = models.Transaction(
                amount=fund.amount,
                description=f"Zasilenie celu: {goal.name}",
                date=date.today(),
                type="transfer",
                account_id=source_acc.id,
                target_account_id=target_acc.id,
                status="zrealizowana"
            )
            db.add(transfer_tx)
            db.flush()
            
            # Aktualizuj salda
            utils.update_balance(db, source_acc.id, fund.amount, "transfer", target_acc.id, is_reversal=False)
        
        # Dodaj wpłatę do celu
        contribution = models.GoalContribution(
            goal_id=goal.id,
            amount=fund.amount,
            date=date.today()
        )
        db.add(contribution)
        
        # Zwiększ current_amount
        goal.current_amount = float(goal.current_amount) + fund.amount
        
        db.commit()  # COMMIT wszystkiego naraz
        
    except HTTPException:
        db.rollback()
        raise  # Przepuść HTTPException (to user error, nie system error)
    except Exception as e:
        db.rollback()
        print(f"❌ BŁĄD fund_goal: {e}")
        raise HTTPException(status_code=500, detail=f"Błąd zasilania celu: {str(e)}")
        
        
def withdraw_goal(db: Session, goal_id: int, withdraw: schemas.GoalWithdraw):
    """Wypłaca z celu z atomową aktualizacją sald"""
    
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Cel nie istnieje")
    
    if float(goal.current_amount) < withdraw.amount:
        raise HTTPException(status_code=400, detail="Brak wystarczających środków na celu")
    
    target_acc = db.query(models.Account).filter(models.Account.id == withdraw.target_account_id).first()
    if not target_acc:
        raise HTTPException(status_code=404, detail="Konto docelowe nie istnieje")

    try:
        # Zmniejsz current_amount
        goal.current_amount = float(goal.current_amount) - withdraw.amount
        
        # Dodaj ujemną wpłatę (audyt)
        db.add(models.GoalContribution(
            goal_id=goal.id,
            amount=-withdraw.amount,
            date=date.today()
        ))
        
        # Jeśli cel jest na innym koncie niż docelowe - utwórz transfer
        if goal.account_id != target_acc.id:
            source_acc = db.query(models.Account).filter(models.Account.id == goal.account_id).first()
            
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
            db.flush()
            
            utils.update_balance(db, source_acc.id, withdraw.amount, "transfer", target_acc.id, is_reversal=False)
        
        db.commit()
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ BŁĄD withdraw_goal: {e}")
        raise HTTPException(status_code=500, detail=f"Błąd wypłaty z celu: {str(e)}")
        

def transfer_goal(db: Session, goal_id: int, transfer: schemas.GoalTransfer):
    """Transfer między celami z atomową aktualizacją"""
    
    source = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    target = db.query(models.Goal).filter(models.Goal.id == transfer.target_goal_id).first()
    
    if not source or not target:
        raise HTTPException(status_code=404, detail="Cel nie istnieje")
    
    if float(source.current_amount) < transfer.amount:
        raise HTTPException(status_code=400, detail="Brak środków na celu źródłowym")
    
    try:
        # Zmniejsz source
        source.current_amount = float(source.current_amount) - transfer.amount
        
        # Zwiększ target
        target.current_amount = float(target.current_amount) + transfer.amount
        
        # Dodaj wpłaty (audyt)
        db.add(models.GoalContribution(
            goal_id=source.id,
            amount=-transfer.amount,
            date=date.today()
        ))
        db.add(models.GoalContribution(
            goal_id=target.id,
            amount=transfer.amount,
            date=date.today()
        ))
        
        db.commit()
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ BŁĄD transfer_goal: {e}")
        raise HTTPException(status_code=500, detail=f"Błąd transferu między celami: {str(e)}")
