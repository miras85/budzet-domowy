from sqlalchemy.orm import Session
from database import SessionLocal
import models

def recalculate_balances():
    db = SessionLocal()
    
    # Dla każdego konta
    accounts = db.query(models.Account).all()
    
    for acc in accounts:
        print(f"\n🔍 Przeliczam konto: {acc.name}")
        print(f"   Obecne saldo: {acc.balance}")
        
        # Suma przychodów (income na to konto)
        income = db.query(models.Transaction).filter(
            models.Transaction.account_id == acc.id,
            models.Transaction.type == 'income',
            models.Transaction.status == 'zrealizowana'
        ).all()
        
        income_sum = sum(float(t.amount) for t in income)
        
        # Suma wydatków (expense z tego konta)
        expenses = db.query(models.Transaction).filter(
            models.Transaction.account_id == acc.id,
            models.Transaction.type == 'expense',
            models.Transaction.status == 'zrealizowana'
        ).all()
        
        expense_sum = sum(float(t.amount) for t in expenses)
        
        # Transfery wychodzące (z tego konta)
        transfers_out = db.query(models.Transaction).filter(
            models.Transaction.account_id == acc.id,
            models.Transaction.type == 'transfer',
            models.Transaction.status == 'zrealizowana'
        ).all()
        
        transfers_out_sum = sum(float(t.amount) for t in transfers_out)
        
        # Transfery przychodzące (na to konto)
        transfers_in = db.query(models.Transaction).filter(
            models.Transaction.target_account_id == acc.id,
            models.Transaction.type == 'transfer',
            models.Transaction.status == 'zrealizowana'
        ).all()
        
        transfers_in_sum = sum(float(t.amount) for t in transfers_in)
        
        # Oblicz prawidłowe saldo
        correct_balance = income_sum - expense_sum - transfers_out_sum + transfers_in_sum
        
        print(f"   Przychody: +{income_sum}")
        print(f"   Wydatki: -{expense_sum}")
        print(f"   Transfery OUT: -{transfers_out_sum}")
        print(f"   Transfery IN: +{transfers_in_sum}")
        print(f"   PRAWIDŁOWE saldo: {correct_balance}")
        
        if abs(float(acc.balance) - correct_balance) > 0.01:
            print(f"   ⚠️  RÓŻNICA: {float(acc.balance) - correct_balance:.2f} zł")
            print(f"   🔧 POPRAWIAM...")
            acc.balance = correct_balance
        else:
            print(f"   ✅ Saldo poprawne")
    
    db.commit()
    db.close()
    print("\n✅ Przeliczenie zakończone!")

if __name__ == "__main__":
    recalculate_balances()
