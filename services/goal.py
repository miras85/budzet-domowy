from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from datetime import date
import models, schemas, utils

def fund_goal(db: Session, goal_id: int, fund: schemas.GoalFund):
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
    
    contribution = models.GoalContribution(goal_id=goal.id, amount=fund.amount, date=date.today())
    db.add(contribution)
    
    goal.current_amount = float(goal.current_amount) + fund.amount
    db.commit()

def withdraw_goal(db: Session, goal_id: int, withdraw: schemas.GoalWithdraw):
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal: raise HTTPException(status_code=404)
    
    if float(goal.current_amount) < withdraw.amount:
        raise HTTPException(status_code=400, detail="Brak wystarczających środków na celu")
    
    target_acc = db.query(models.Account).filter(models.Account.id == withdraw.target_account_id).first()
    if not target_acc: raise HTTPException(status_code=404, detail="Konto docelowe nie istnieje")

    goal.current_amount = float(goal.current_amount) - withdraw.amount
    db.add(models.GoalContribution(goal_id=goal.id, amount=-withdraw.amount, date=date.today()))
    
    if goal.account_id != target_acc.id:
        source_acc = db.query(models.Account).filter(models.Account.id == goal.account_id).first()
        tx = models.Transaction(amount=withdraw.amount, description=f"Wypłata z celu: {goal.name}", date=date.today(), type="transfer", account_id=source_acc.id, target_account_id=target_acc.id, status="zrealizowana")
        db.add(tx)
        utils.update_balance(db, source_acc.id, withdraw.amount, "transfer", target_acc.id, is_reversal=False)
    
    db.commit()

def transfer_goal(db: Session, goal_id: int, transfer: schemas.GoalTransfer):
    source = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    target = db.query(models.Goal).filter(models.Goal.id == transfer.target_goal_id).first()
    if not source or not target: raise HTTPException(status_code=404)
    if float(source.current_amount) < transfer.amount: raise HTTPException(status_code=400, detail="Brak środków")
    
    source.current_amount = float(source.current_amount) - transfer.amount
    target.current_amount = float(target.current_amount) + transfer.amount
    
    db.add(models.GoalContribution(goal_id=source.id, amount=-transfer.amount, date=date.today()))
    db.add(models.GoalContribution(goal_id=target.id, amount=transfer.amount, date=date.today()))
    db.commit()
