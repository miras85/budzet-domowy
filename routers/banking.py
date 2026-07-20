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

    # Licznik dzienny z resetem na nowy dzień (bez zapisu do bazy — tylko odczyt)
    today = datetime.now().date()
    if session.sync_count_date == today:
        syncs_used = session.sync_count_today or 0
    else:
        syncs_used = 0

    return {
        "connected": True,
        "bank_name": session.bank_name,
        "status": session.status,
        "valid_until": str(session.valid_until),
        "last_sync": str(session.last_sync) if session.last_sync else None,
        "syncs_used_today": syncs_used,
        "syncs_remaining_today": max(0, 4 - syncs_used)
    }
@router.post("/sync")
def sync_transactions(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Podgląd transakcji z banku (bez zapisu) — max 4x/24h + debounce 60s"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin może synchronizować")

    session = db.query(models.BankSession).filter(
        models.BankSession.user_id == current_user.id,
        models.BankSession.status == "active"
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Brak aktywnego połączenia z bankiem")

    from datetime import timezone

    # Throttling krótkoterminowy — min 60 sekund między KAŻDĄ próbą (nawet nieudaną)
    if session.last_sync:
        now = datetime.now(timezone.utc)
        last = session.last_sync
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        seconds_since_last = (now - last).total_seconds()
        if seconds_since_last < 60:
            wait = int(60 - seconds_since_last)
            raise HTTPException(
                status_code=429,
                detail=f"Poczekaj jeszcze {wait} sekund przed kolejnym zapytaniem (ochrona przed spam)."
            )

    # Throttling PSD2 — max 4 synchronizacje / 24h (tylko udane)
    today = datetime.now().date()
    if session.sync_count_date == today:
        if session.sync_count_today >= 4:
            raise HTTPException(
                status_code=429,
                detail=f"Limit ING: maksymalnie 4 synchronizacje dziennie. Użyto: {session.sync_count_today}/4. Reset o północy."
            )
    else:
        # Nowy dzień — reset licznika
        session.sync_count_today = 0
        session.sync_count_date = today

    # Zapisz próbę NATYCHMIAST (dla debounce) — niezależnie od wyniku
    session.last_sync = datetime.now()
    db.commit()

    try:
        accounts = banking_service.get_session_accounts(session.session_id)
        if not accounts:
            raise HTTPException(status_code=404, detail="Brak kont w sesji")

        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")

        all_transactions = []
        for account in accounts:
            account_uid = account.get("uid")
            txs = banking_service.get_transactions(
                session.session_id, account_uid, date_from, date_to
            )
            all_transactions.extend(txs)

        ror_account = db.query(models.Account).filter(
            models.Account.user_id == current_user.id,
            models.Account.is_savings == False
        ).first()
        account_id = ror_account.id if ror_account else 1

        parsed = parse_ing_transactions(
            all_transactions, account_id,
            db=db, user_id=current_user.id
        )

        # SUKCES — zwiększ licznik dzienny
        session.sync_count_today = (session.sync_count_today or 0) + 1
        session.sync_count_date = today
        db.commit()

        return {
            "status": "synced",
            "transactions_count": len(parsed),
            "syncs_used_today": session.sync_count_today,
            "syncs_remaining_today": 4 - session.sync_count_today,
            "preview": parsed[:5]
        }

    except HTTPException:
        # BŁĄD (np. 429 z ING) — last_sync już zapisany wyżej, licznik dzienny NIE rośnie
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
def import_transactions(
    date_from: str,
    date_to: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Importuje transakcje z banku do bazy za podany okres"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin może importować")

    session = db.query(models.BankSession).filter(
        models.BankSession.user_id == current_user.id,
        models.BankSession.status == "active"
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Brak aktywnego połączenia z bankiem")

    try:
        accounts = banking_service.get_session_accounts(session.session_id)
        if not accounts:
            raise HTTPException(status_code=404, detail="Brak kont w sesji")

        all_transactions = []
        for account in accounts:
            account_uid = account.get("uid")
            txs = banking_service.get_transactions(
                session.session_id, account_uid, date_from, date_to
            )
            all_transactions.extend(txs)

        ror_account = db.query(models.Account).filter(
            models.Account.user_id == current_user.id,
            models.Account.is_savings == False
        ).first()
        account_id = ror_account.id if ror_account else 1

        parsed = parse_ing_transactions(
            all_transactions, account_id,
            db=db, user_id=current_user.id
        )

        imported = 0
        skipped = 0
        from utils import update_balance

        for tx_data in parsed:
            # Deduplikacja: data + kwota + opis + konto + typ
            # (spójna z importem CSV — save_imported_transactions)
            existing = db.query(models.Transaction).filter(
                models.Transaction.date == tx_data["date"],
                models.Transaction.amount == tx_data["amount"],
                models.Transaction.description == tx_data["description"],
                models.Transaction.account_id == tx_data["account_id"],
                models.Transaction.type == tx_data["type"]
            ).first()

            if existing:
                skipped += 1
                continue

            new_tx = models.Transaction(
                date=tx_data["date"],
                amount=tx_data["amount"],
                description=tx_data["description"],
                type=tx_data["type"],
                status="zrealizowana",
                account_id=tx_data["account_id"],
                target_account_id=tx_data.get("target_account_id"),
                category_id=tx_data.get("category_id")
            )
            db.add(new_tx)
            db.flush()

            # Zaktualizuj saldo
            update_balance(
                db,
                tx_data["account_id"],
                tx_data["amount"],
                tx_data["type"],
                tx_data.get("target_account_id"),
                is_reversal=False
            )

            imported += 1

        # Zwiększ licznik dzienny (import też zużywa limit ING) z resetem na nowy dzień
        today = datetime.now().date()
        if session.sync_count_date != today:
            session.sync_count_today = 0
            session.sync_count_date = today
        session.sync_count_today = (session.sync_count_today or 0) + 1
        session.sync_count_date = today

        session.last_sync = datetime.now()
        db.commit()

        return {
            "status": "imported",
            "imported": imported,
            "skipped": skipped,
            "total": len(parsed),
            "syncs_used_today": session.sync_count_today,
            "syncs_remaining_today": max(0, 4 - session.sync_count_today),
            "period": f"{date_from} → {date_to}"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
