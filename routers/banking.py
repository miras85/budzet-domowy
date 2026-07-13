# routers/banking.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import database, models
from services import banking as banking_service
from services.banking import parse_ing_transactions

router = APIRouter(prefix="/api/banking", tags=["Banking"])


@router.get("/banks")
def get_banks(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Lista dostępnych banków"""
    banks = banking_service.get_available_banks("PL")
    return {"banks": [{"name": b["name"], "logo": b["logo"]} for b in banks]}


@router.post("/connect")
def connect_bank(
    bank_name: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Rozpoczyna połączenie z bankiem — zwraca URL autoryzacji"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin może łączyć konto bankowe")
    auth_url = banking_service.start_bank_auth(bank_name)
    return {"auth_url": auth_url}


@router.get("/callback")
def banking_callback(
    code: str,
    request: Request,
    db: Session = Depends(database.get_db)
):
    """Callback po autoryzacji w banku."""
    try:
        session_data = banking_service.create_session(code)
        session_id = session_data.get("session_id") or session_data.get("id")

        user = db.query(models.User).filter(
            models.User.role == "admin"
        ).first()

        if not user:
            return RedirectResponse("/?banking=error")

        existing = db.query(models.BankSession).filter(
            models.BankSession.user_id == user.id
        ).first()

        if existing:
            existing.session_id = session_id
            existing.status = "active"
            existing.valid_until = datetime.now(timezone.utc) + timedelta(days=90)
            existing.last_sync = None
        else:
            bank_session = models.BankSession(
                user_id=user.id,
                session_id=session_id,
                bank_name="ING Bank Śląski",
                bank_country="PL",
                status="active",
                valid_until=datetime.now(timezone.utc) + timedelta(days=90)
            )
            db.add(bank_session)

        db.commit()
        return RedirectResponse("/?banking=success")

    except Exception as e:
        print(f"❌ Banking callback error: {e}")
        return RedirectResponse("/?banking=error")


@router.get("/status")
def get_banking_status(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Sprawdza status połączenia z bankiem"""
    owner_id = database.get_data_owner_id(current_user, db)
    session = db.query(models.BankSession).filter(
        models.BankSession.user_id == owner_id
    ).first()

    if not session:
        return {"connected": False}

    return {
        "connected": True,
        "bank_name": session.bank_name,
        "status": session.status,
        "valid_until": str(session.valid_until),
        "last_sync": str(session.last_sync) if session.last_sync else None
    }


@router.post("/sync")
def sync_transactions(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Synchronizuje transakcje z banku"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin może synchronizować")

    session = db.query(models.BankSession).filter(
        models.BankSession.user_id == current_user.id,
        models.BankSession.status == "active"
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Brak aktywnego połączenia z bankiem")

    try:
        # Pobierz konta z sesji
        accounts = banking_service.get_session_accounts(session.session_id)

        if not accounts:
            raise HTTPException(status_code=404, detail="Brak kont w sesji")

        # Pobierz transakcje z ostatnich 30 dni
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")

        all_transactions = []
        for account in accounts:
            account_uid = account.get("uid") or account.get("id")
            txs = banking_service.get_transactions(
                session.session_id,
                account_uid,
                date_from,
                date_to
            )
            all_transactions.extend(txs)

        # Znajdź konto ROR usera
        ror_account = db.query(models.Account).filter(
            models.Account.user_id == current_user.id,
            models.Account.is_savings == False
        ).first()
        account_id = ror_account.id if ror_account else 1

        # Parsuj transakcje do formatu DomowyBudżet
        parsed = parse_ing_transactions(all_transactions, account_id)

        # Zaktualizuj last_sync
        session.last_sync = datetime.now(timezone.utc)
        db.commit()

        return {
            "status": "synced",
            "transactions_count": len(parsed),
            "preview": parsed[:5]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
def import_transactions(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Importuje transakcje z banku do bazy DomowyBudżet"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin może importować")

    session = db.query(models.BankSession).filter(
        models.BankSession.user_id == current_user.id,
        models.BankSession.status == "active"
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Brak aktywnego połączenia z bankiem")

    try:
        # Pobierz konta z sesji
        accounts = banking_service.get_session_accounts(session.session_id)
        if not accounts:
            raise HTTPException(status_code=404, detail="Brak kont w sesji")

        # Pobierz transakcje z ostatnich 30 dni
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")

        all_transactions = []
        for account in accounts:
            account_uid = account.get("uid")
            txs = banking_service.get_transactions(
                session.session_id,
                account_uid,
                date_from,
                date_to
            )
            all_transactions.extend(txs)

        # Znajdź konto ROR usera
        ror_account = db.query(models.Account).filter(
            models.Account.user_id == current_user.id,
            models.Account.is_savings == False
        ).first()
        account_id = ror_account.id if ror_account else 1

        # Parsuj transakcje
        parsed = parse_ing_transactions(all_transactions, account_id)

        # Zapisz do bazy z deduplikacją
        imported = 0
        skipped = 0

        for tx_data in parsed:
            # Sprawdź duplikat po reference + account_id
            reference = tx_data.get("reference", "")
            existing = db.query(models.Transaction).filter(
                models.Transaction.description.like(f"%{reference}%")
            ).first() if reference else None

            if existing:
                skipped += 1
                continue

            # Utwórz nową transakcję
            new_tx = models.Transaction(
                date=tx_data["date"],
                amount=tx_data["amount"],
                description=tx_data["description"],
                type=tx_data["type"],
                status="zrealizowana",
                account_id=tx_data["account_id"],
                category_id=None  # Auto-kategoryzacja w przyszłości
            )
            db.add(new_tx)

            # Zaktualizuj saldo konta
            from utils import update_balance
            update_balance(db, account_id, tx_data["amount"], tx_data["type"],
                         None, is_reversal=False)

            imported += 1

        # Zaktualizuj last_sync
        session.last_sync = datetime.now(timezone.utc)
        db.commit()

        return {
            "status": "imported",
            "imported": imported,
            "skipped": skipped,
            "total": len(parsed)
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
