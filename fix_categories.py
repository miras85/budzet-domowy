import sys
import os

# Dodajemy ścieżkę, żeby Python widział nasze moduły
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from sqlalchemy import or_
import database, models

def fix_loan_categories():
    print("--- ROZPOCZYNAM NAPRAWĘ KATEGORII (WERSJA 2) ---")
    
    try:
        db = database.SessionLocal()
    except Exception as e:
        print(f"BŁĄD: Nie udało się połączyć z bazą: {e}")
        return

    # 1. Znajdź lub stwórz kategorię "Spłata zobowiązań"
    target_cat_name = "Spłata zobowiązań"
    category = db.query(models.Category).filter(models.Category.name == target_cat_name).first()
    
    if not category:
        print(f"-> Tworzę nową kategorię: '{target_cat_name}'")
        category = models.Category(name=target_cat_name)
        db.add(category)
        db.commit()
        db.refresh(category)
    else:
        print(f"-> Kategoria '{target_cat_name}' istnieje (ID: {category.id})")

    # 2. Pobierz WSZYSTKIE transakcje kredytowe (bez filtrowania kategorii w SQL)
    # Używamy .isnot(None) dla pewności
    transactions = db.query(models.Transaction).filter(
        models.Transaction.loan_id.isnot(None)
    ).all()
    
    print(f"-> Znaleziono łącznie {len(transactions)} transakcji powiązanych z kredytami.")
    
    count = 0
    for tx in transactions:
        # Sprawdzamy w Pythonie: czy kategoria jest pusta LUB inna niż docelowa
        if tx.category_id != category.id:
            old_cat = tx.category_id if tx.category_id else "BRAK"
            print(f"   [NAPRAWA] ID: {tx.id} | Opis: {tx.description} | Stara kat: {old_cat}")
            
            tx.category_id = category.id
            count += 1
    
    if count > 0:
        db.commit()
        print(f"--- ZAPISANO ZMIANY DLA {count} TRANSAKCJI ---")
    else:
        print("--- WSZYSTKIE TRANSAKCJE MAJĄ JUŻ POPRAWNĄ KATEGORIĘ ---")

    db.close()

if __name__ == "__main__":
    fix_loan_categories()
