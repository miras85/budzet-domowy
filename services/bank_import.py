import io
import re
from datetime import datetime
from typing import Tuple, Optional, List
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException
import models, schemas
import utils
from services import categorization

def normalize_amount(value: str) -> float:
    """
    Parsuje kwotę z różnych formatów ING:
    - "-157 99" (spacja/tab między zł a gr)
    - "-157,99" (przecinek)
    - "-157.99" (kropka)
    Zwraca float z ZACHOWANIEM ZNAKU (+ lub -)
    """
    if not value:
        return 0.0
    
    # 1. Usuń śmieci
    val = value.replace('PLN', '').replace('EUR', '').strip()
    val = val.replace('"', '').replace("'", "")
    
    # 2. Zachowaj znak minus (jeśli jest)
    is_negative = val.startswith('-')
    val = val.lstrip('-').strip()  # Usuń minus tymczasowo
    
    # 3. ING Format: "120 00" lub "120    00" (spacja/tab przed groszami)
    if ',' not in val and '.' not in val:
        # Sprawdź czy to format "XXX YY" (spacja/tab między zł a gr)
        match_space_sep = re.match(r'^(\d+)[\s\t]+(\d{2})$', val)
        if match_space_sep:
            val = f"{match_space_sep.group(1)}.{match_space_sep.group(2)}"
        # Jeśli nie pasuje - zostaw jak jest (może być cała liczba bez groszy)
    
    # 4. Standardowy format (usuń spacje, zamień przecinek na kropkę)
    val = val.replace(' ', '').replace('\xa0', '').replace('\t', '')
    val = val.replace(',', '.')
    
    try:
        result = float(val)
        # Przywróć znak minus jeśli był
        return -result if is_negative else result
    except ValueError:
        print(f"⚠️ WARNING: Nie można sparsować kwoty: '{value}'")
        return 0.0

def auto_categorize(db: Session, description: str, amount: float,
                    user_id: Optional[int] = None) -> Tuple[Optional[int], str]:
    """
    Auto-kategoryzacja na podstawie historii.
    TYP (income/expense) jest ZAWSZE określany przez ZNAK kwoty z CSV!
    Szukamy tylko KATEGORII z podobnych transakcji.

    WAŻNE: dopasowanie jest ograniczone do transakcji WŁAŚCICIELA (user_id),
    żeby nie podpowiadać kategorii z danych innego użytkownika.

    Sam dobór kategorii deleguje do warstwowego silnika
    services/categorization.suggest_category (learned -> static -> history),
    aby import CSV i import ING zachowywały się identycznie.
    """
    tx_type = "expense" if amount < 0 else "income"

    if user_id is None:
        return None, tx_type

    category_id = categorization.suggest_category(
        db, user_id=user_id, tx_type=tx_type, description=description,
    )
    return category_id, tx_type

async def parse_bank_csv(db: Session, file: UploadFile, user_id: Optional[int] = None):
    content = await file.read()
    
    # 1. Wykrywanie kodowania
    text = ""
    for enc in ['cp1250', 'utf-8', 'latin-1']:
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
            
    if not text:
        raise HTTPException(status_code=400, detail="Nieznane kodowanie pliku")

    lines = text.splitlines()
    
    # 2. Szukanie nagłówka
    header_row_idx = -1
    for i, line in enumerate(lines):
        if "Data transakcji" in line or "Data operacji" in line:
            header_row_idx = i
            break
    
    # Fallback
    if header_row_idx == -1:
        for i, line in enumerate(lines):
            if "Data" in line and "Kwota" in line:
                header_row_idx = i
                break

    if header_row_idx == -1:
        raise HTTPException(status_code=400, detail="Nie znaleziono nagłówka 'Data transakcji'")

    # 3. Parsowanie nagłówka
    header_line = lines[header_row_idx]
    clean_header = header_line.replace('"', '').replace("'", "")
    headers = clean_header.split(';')
    
    # 4. Mapowanie kolumn (Szukamy WSZYSTKICH potencjalnych kolumn z kwotą)
    col_date = -1
    col_desc_1 = -1
    col_desc_2 = -1
    
    # Lista priorytetowa kolumn z kwotami
    col_amount_main = -1   # "Kwota transakcji"
    col_amount_block = -1  # "Kwota blokady"
    col_amount_curr = -1   # "Kwota płatności w walucie"
    
    clean_headers = [h.strip().lower() for h in headers]
    
    for idx, h in enumerate(clean_headers):
        if "data transakcji" in h: col_date = idx
        elif "dane kontrahenta" in h: col_desc_1 = idx
        elif "tytuł" in h or "tytul" in h: col_desc_2 = idx
        
        # Mapowanie kwot
        elif "kwota transakcji" in h: col_amount_main = idx
        elif "kwota blokady" in h: col_amount_block = idx
        elif "kwota płatności" in h: col_amount_curr = idx
        elif "kwota" in h and col_amount_main == -1: col_amount_main = idx
        
    if col_date == -1:
        raise HTTPException(status_code=400, detail=f"Nie znaleziono kolumny 'Data'. Nagłówki: {headers}")
    
    # Jeśli nie znaleziono głównej, użyjemy którejkolwiek innej jako głównej
    if col_amount_main == -1:
        if col_amount_block != -1: col_amount_main = col_amount_block
        elif col_amount_curr != -1: col_amount_main = col_amount_curr
        else:
            raise HTTPException(status_code=400, detail=f"Nie znaleziono kolumny 'Kwota'. Nagłówki: {headers}")

    # 5. Przetwarzanie danych
    preview_data = []
    errors_log = []
    rows_processed = 0
    
    for line in lines[header_row_idx+1:]:
        if not line.strip(): continue
        
        try:
            row = line.split(';')
            row = [r.strip().strip('"').strip("'") for r in row]
            
            # Sprawdzamy czy wiersz jest wystarczająco długi dla daty
            if len(row) <= col_date: continue

            raw_date = row[col_date].strip()
            if not raw_date or len(raw_date) < 8: continue

            # --- LOGIKA WYBORU KWOTY ---
            raw_amount = ""
            
            # 1. Sprawdź główną kolumnę (Kwota transakcji)
            if len(row) > col_amount_main and row[col_amount_main].strip():
                raw_amount = row[col_amount_main].strip()
            
            # 2. Jeśli pusta, sprawdź Kwotę Blokady (dla płatności kartą)
            if not raw_amount and col_amount_block != -1 and len(row) > col_amount_block:
                raw_amount = row[col_amount_block].strip()
                
            # 3. Jeśli nadal pusta, sprawdź Kwotę w walucie
            if not raw_amount and col_amount_curr != -1 and len(row) > col_amount_curr:
                raw_amount = row[col_amount_curr].strip()
            
            # Jeśli nadal pusta, to prawdopodobnie wiersz techniczny -> pomiń
            if not raw_amount:
                continue
            # ---------------------------

            # Opis
            desc_parts = []
            if col_desc_1 != -1 and len(row) > col_desc_1: desc_parts.append(row[col_desc_1].strip())
            if col_desc_2 != -1 and len(row) > col_desc_2: desc_parts.append(row[col_desc_2].strip())
            description = " | ".join([p for p in desc_parts if p])
            if not description: description = "Importowana transakcja"

            # Kwota
            amount = normalize_amount(raw_amount)
            
            # Data
            date_obj = None
            clean_date_str = raw_date[:10]
            for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d"]:
                try:
                    date_obj = datetime.strptime(clean_date_str, fmt).date()
                    break
                except ValueError:
                    continue
            
            if not date_obj:
                errors_log.append(f"Niepoprawny format daty '{raw_date}'")
                continue

            cat_id, tx_type = auto_categorize(db, description, amount, user_id)

            preview_data.append({
                "date": str(date_obj),
                "description": description,
                "amount": abs(amount),
                "type": tx_type,
                "category_id": cat_id,
                "ignore": False
            })
            rows_processed += 1
            
        except Exception as e:
            errors_log.append(f"Błąd: {str(e)}")
            continue

    if not preview_data:
        msg = "Nie udało się odczytać transakcji."
        if errors_log:
            msg += f" Przykładowe błędy: {'; '.join(errors_log[:3])}"
        raise HTTPException(status_code=400, detail=msg)

    return preview_data

def save_imported_transactions(db: Session, account_id: int, transactions: List[schemas.TransactionImport]):
    """Importuje transakcje z atomowym zapisem (albo wszystko, albo nic)"""
    
    count = 0
    skipped = 0
    print(f"--- PRÓBA ZAPISU {len(transactions)} TRANSAKCJI ---")
    
    try:
        for tx in transactions:
            if tx.ignore:
                continue
            
            # Walidacja kategorii
            cat_id = tx.category_id
            if not cat_id or cat_id == 0 or cat_id == "0":
                cat_id = None
            
            # Walidacja kwoty
            amount = float(tx.amount)
            
            # Walidacja daty
            tx_date = tx.date
            if isinstance(tx_date, str):
                tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()

            # Sprawdzenie duplikatu
            existing = db.query(models.Transaction).filter(
                models.Transaction.date == tx_date,
                models.Transaction.amount == abs(amount),
                models.Transaction.description == tx.description,
                models.Transaction.account_id == account_id,
                models.Transaction.type == tx.type
            ).first()
            
            if existing:
                print(f"⏭️  SKIP: Duplikat '{tx.description}' z {tx_date} ({abs(amount)} zł)")
                skipped += 1
                continue

            # Dodaj transakcję
            new_tx = models.Transaction(
                amount=abs(amount),
                description=tx.description,
                date=tx_date,
                type=tx.type,
                account_id=account_id,
                category_id=cat_id,
                status="zrealizowana"
            )
            
            db.add(new_tx)
            db.flush()  # Flush (nie commit) - dostaniemy ID
            
            # Aktualizacja salda
            utils.update_balance(db, account_id, abs(amount), tx.type, None, is_reversal=False)
            count += 1
        
        # COMMIT WSZYSTKICH transakcji naraz (atomowo)
        db.commit()
        print(f"--- ✅ SUKCES: ZAPISANO {count} TRANSAKCJI, POMINIĘTO {skipped} DUPLIKATÓW ---")
        return {"imported": count, "skipped": skipped}
        
    except Exception as e:
        db.rollback()
        print(f"--- ❌ BŁĄD: {e} ---")
        print(f"--- 🔄 ROLLBACK: Cofnięto wszystkie zmiany ---")
        raise HTTPException(status_code=500, detail=f"Błąd importu: {str(e)}")
