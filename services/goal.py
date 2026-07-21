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
    """Wypłaca z celu z opcjonalną archiwizacją"""
    
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
        
        # Transfer środków jeśli inne konto
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
        
        # NOWE: Archiwizuj po wypłacie jeśli zaznaczono checkbox
        if hasattr(withdraw, 'archive_after') and withdraw.archive_after:
            goal.is_archived = True
        
        db.commit()
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd wypłaty: {str(e)}")

def reconcile_savings_goals(db: Session, user_id: int):
    """Uzgadnia rezerwacje celów z realnym saldem kont oszczędnościowych.

    Po imporcie przelewów saldo konta oszczędnościowego mogło spaść poniżej sumy
    rezerwacji celów (current_amount). Wtedy 'dostępne' schodzi na minus, a cele
    pokazują pieniądze, których już nie ma.

    Zasada (ustalona z użytkownikiem):
    - Jeśli saldo >= suma rezerwacji -> nic nie ruszamy (przelew zjadł tylko wolne
      środki).
    - Jeśli saldo < suma rezerwacji -> obniżamy cele o brakującą kwotę, zaczynając
      od NAJNOWSZEGO celu (id malejąco), aż suma rezerwacji zrówna się z saldem.

    Nie robi commitu — wywoływać wewnątrz transakcji (import robi commit sam).
    Zwraca listę korekt do zalogowania.
    """
    adjustments = []

    savings_accounts = db.query(models.Account).filter(
        models.Account.user_id == user_id,
        models.Account.is_savings == True
    ).all()

    for acc in savings_accounts:
        balance = float(acc.balance)

        # Cele tego konta, od najnowszego (spójne z finance.py: bez filtra is_archived)
        goals = db.query(models.Goal).filter(
            models.Goal.account_id == acc.id,
            models.Goal.user_id == user_id
        ).order_by(models.Goal.id.desc()).all()

        reserved = sum(float(g.current_amount or 0) for g in goals)
        shortfall = reserved - balance

        # Tolerancja groszowa, żeby nie ruszać celów przy zaokrągleniach
        if shortfall <= 0.005:
            continue

        for goal in goals:
            if shortfall <= 0.005:
                break
            current = float(goal.current_amount or 0)
            if current <= 0:
                continue
            cut = min(current, shortfall)
            goal.current_amount = current - cut
            shortfall -= cut

            # Wpis audytowy (ujemny) — spójny z ręczną wypłatą z celu
            db.add(models.GoalContribution(
                goal_id=goal.id,
                amount=-cut,
                date=date.today()
            ))
            adjustments.append((goal.id, goal.name, cut))
            print(f"[RECONCILE] Cel '{goal.name}' (id={goal.id}) obniżony o "
                  f"{cut:.2f} zł (konto '{acc.name}' saldo={balance:.2f})")

    return adjustments


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
