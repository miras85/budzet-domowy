import csv
import io
import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import UploadFile, HTTPException
import models, schemas

def normalize_amount(value: str) -> float:
    """
    Konwertuje dziwne formaty kwot bankowych na float.
    Obsługuje:
    - "120,00" -> 120.0
    - "-120 00" -> -120.0 (spacja/tab jako separator)
    - "1 200,50" -> 1200.5
    """
    if not value:
        return 0.0
    
    # Usuń waluty i białe znaki (poza tymi w środku liczby)
    val = value.replace('PLN', '').replace('EUR', '').strip()
    val = val.replace('"', '').replace("'", "")
    
    # Przypadek 1: Spacja/Tab jako separator dziesiętny (np. "-120 00" lub "-120\t00")
    # Szukamy wzorca: (opcjonalny minus)(cyfry)(spacja/tab)(dokładnie dwie cyfry na końcu)
    match_space_sep = re.match(r'^(-?\d+)[\s\t]+(\d{2})$', val)
    if match_space_sep:
        return float(f"{match_space_sep.group(1)}.{match_space_sep.group(2)}")

    # Przypadek 2: Standardowy (1 200,00 lub 1.200,00)
    # Usuwamy spacje (tysiączne)
    val = val.replace(' ', '').replace('\xa0', '') # \xa0 to twarda spacja
    val = val.replace(',', '.')
    
    try:
        return float(val)
    except ValueError:
        return 0.0

def auto_categorize(db: Session, description: str, amount: float) -> tuple[int | None, str]:
    """
    Próbuje zgadnąć kategorię i typ na podstawie historii transakcji.
    Zwraca (category_id, type).
    """
    # 1. Domyślny typ na podstawie kwoty
    tx_type = "expense" if amount < 0 else "income"
    
    # 2. Szukamy w bazie transakcji o podobnym opisie
    # Używamy prostego dopasowania LIKE %keyword% dla słów z opisu
    # Bierzemy pierwsze znaczące słowo (min 4 znaki)
    words = [w for w in re.split(r'\s+', description) if len(w) > 3]
    
    if not words:
        return None, tx_type

    # Szukamy ostatniej transakcji zawierającej jedno ze słów kluczowych
    # (W prawdziwej produkcji można tu użyć Fuzzy Search, ale SQL LIKE wystarczy na start)
    keyword = words[0]
    similar_tx = db.query(models.Transaction)\
        .filter(models.Transaction.description.ilike(f"%{keyword}%"))\
        .filter(models.Transaction.category_id.isnot(None))\
        .order_by(models.Transaction.date.desc())\
        .first()

    if similar_tx:
        return similar_tx.category_id, similar_tx.type
    
    return None, tx_type

async def parse_bank_csv(db: Session, file: UploadFile):
    content = await file.read()
    
    # Próba dekodowania (CP1250 jest standardem w PL bankach, UTF-8 fallback)
    try:
        text = content.decode('cp1250')
    except UnicodeDecodeError:
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('latin-1') # Ostateczność

    lines = text.splitlines()
    
    # Szukanie nagłówka (pomijanie metadanych ING)
    header_row_idx = -1
    for i, line in enumerate(lines):
        if "Data transakcji" in line or "Data operacji" in line:
            header_row_idx = i
            break
    
    if header_row_idx == -1:
        raise HTTPException(status_code=400, detail="Nie znaleziono nagłówka 'Data transakcji' w pliku.")

    # Parsowanie CSV od linii nagłówka
    # Używamy csv.reader, który radzi sobie z cudzysłowami lepiej niż split(';')
    csv_io = io.StringIO('\n'.join(lines[header_row_idx:]))
    reader = csv.reader(csv_io, delimiter=';')
    
    headers = next(reader) # Pierwszy wiersz to nagłówki
    
    # Mapowanie kolumn (szukamy indeksów)
    try:
        # ING specyficzne nazwy
        col_date = -1
        col_desc_1 = -1 # Dane kontrahenta
        col_desc_2 = -1 # Tytuł
        col_amount = -1
        
        for idx, h in enumerate(headers):
            h_lower = h.lower().strip()
            if "data transakcji" in h_lower: col_date = idx
            elif "dane kontrahenta" in h_lower: col_desc_1 = idx
            elif "tytuł" in h_lower or "tytul" in h_lower: col_desc_2 = idx
            elif "kwota transakcji" in h_lower: col_amount = idx
            
        if col_date == -1 or col_amount == -1:
            raise Exception("Brak wymaganych kolumn (Data, Kwota)")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Błąd struktury pliku: {str(e)}")

    preview_data = []
    
    for row in reader:
        if not row: continue
        
        # Pobieranie danych
        try:
            raw_date = row[col_date].strip()
            raw_amount = row[col_amount].strip()
            
            # Opis: Łączymy Kontrahenta i Tytuł
            desc_parts = []
            if col_desc_1 != -1 and len(row) > col_desc_1: desc_parts.append(row[col_desc_1].strip())
            if col_desc_2 != -1 and len(row) > col_desc_2: desc_parts.append(row[col_desc_2].strip())
            description = " | ".join([p for p in desc_parts if p])
            if not description: description = "Importowana transakcja"

            # Normalizacja
            amount = normalize_amount(raw_amount)
            
            # Data (ING format: YYYY-MM-DD)
            try:
                date_obj = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                continue # Pomijamy błędne daty (np. podsumowania na dole pliku)

            # Auto-kategoryzacja
            cat_id, tx_type = auto_categorize(db, description, amount)

            preview_data.append({
                "date": str(date_obj),
                "description": description,
                "amount": abs(amount), # Frontend dostaje wartość bezwzględną
                "type": tx_type,       # Typ określa znak
                "category_id": cat_id,
                "raw_amount": raw_amount # Do debugowania
            })
            
        except Exception as e:
            print(f"Skipping row: {row} -> {e}")
            continue

    return preview_data

def save_imported_transactions(db: Session, account_id: int, transactions: list[schemas.TransactionImport]):
    count = 0
    for tx in transactions:
        if tx.ignore: continue
        
        # Tworzymy transakcję używając istniejącej logiki (żeby zaktualizować salda)
        # Musimy przekonwertować TransactionImport na TransactionCreate
        
        # Jeśli typ to wydatek, a kwota jest dodatnia, to w bazie zapisujemy kwotę dodatnią,
        # ale typ 'expense' sprawi, że saldo zmaleje.
        
        tx_create = schemas.TransactionCreate(
            amount=tx.amount,
            description=tx.description,
            date=tx.date,
            type=tx.type,
            account_id=account_id,
            category_name=None, # Kategorię ustawiamy po ID niżej
            status="zrealizowana"
        )
        
        # Ręczne tworzenie modelu, bo musimy podać category_id bezpośrednio
        new_tx = models.Transaction(
            amount=tx_create.amount,
            description=tx_create.description,
            date=tx_create.date,
            type=tx_create.type,
            account_id=tx_create.account_id,
            category_id=tx.category_id,
            status="zrealizowana"
        )
        
        db.add(new_tx)
        
        # Aktualizacja salda
        utils.update_balance(db, account_id, tx.amount, tx.type, None, is_reversal=False)
        count += 1
        
    db.commit()
    return {"imported": count}
