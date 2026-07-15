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
    """Podgląd transakcji z banku (bez zapisu) — max 4x/24h"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin może synchronizować")

    session = db.query(models.BankSession).filter(
        models.BankSession.user_id == current_user.id,
        models.BankSession.status == "active"
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Brak aktywnego połączenia z bankiem")

    # Throttling PSD2 — max 4 synchronizacje / 24h
    today = datetime.now().date()
    if session.sync_count_date == today:
        if session.sync_count_today >= 4:
            # Oblicz kiedy reset
            if session.last_sync:
                from datetime import timezone
                now = datetime.now(timezone.utc)
                last = session.last_sync
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                next_reset = last.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                hours_left = int((next_reset - now).total_seconds() / 3600)
            raise HTTPException(
                status_code=429,
                detail=f"Limit ING: maksymalnie 4 synchronizacje dziennie. Użyto: {session.sync_count_today}/4. Reset o północy."
            )
    else:
        # Nowy dzień — reset licznika
        session.sync_count_today = 0
        session.sync_count_date = today

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

        # Zaktualizuj licznik i last_sync
        session.sync_count_today = (session.sync_count_today or 0) + 1
        session.sync_count_date = today
        session.last_sync = datetime.now()
        db.commit()

        return {
            "status": "synced",
            "transactions_count": len(parsed),
            "syncs_used_today": session.sync_count_today,
            "syncs_remaining_today": 4 - session.sync_count_today,
            "preview": parsed[:5]
        }

    except HTTPException:
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

        for tx_data in parsed:
            # Deduplikacja po reference
            reference = tx_data.get("reference", "")
            if reference:
                existing = db.query(models.Transaction).filter(
                    models.Transaction.description.like(f"%{reference}%")
                ).first()
                if existing:
                    skipped += 1
                    continue

                # Auto-kategoryzacja na podstawie historii
                category_id = None
                if tx_data["type"] != "transfer":
                    # Szukaj podobnej transakcji w historii
                    desc_prefix = tx_data["description"][:25]
                    similar = db.query(models.Transaction).join(
                        models.Account,
                        models.Transaction.account_id == models.Account.id
                    ).filter(
                        models.Account.user_id == current_user.id,
                        models.Transaction.category_id.isnot(None),
                        models.Transaction.type == tx_data["type"],
                        models.Transaction.description.ilike(f"%{desc_prefix}%")
                    ).order_by(models.Transaction.id.desc()).first()

                    if similar:
                        category_id = similar.category_id

                new_tx = models.Transaction(
                    date=tx_data["date"],
                    amount=tx_data["amount"],
                    description=tx_data["description"],
                    type=tx_data["type"],
                    status="zrealizowana",
                    account_id=tx_data["account_id"],
                    target_account_id=tx_data.get("target_account_id"),
                    category_id=category_id
                )
            db.add(new_tx)
            db.flush()

            # Zaktualizuj saldo
            from utils import update_balance
            update_balance(
                db,
                tx_data["account_id"],
                tx_data["amount"],
                tx_data["type"],
                tx_data.get("target_account_id"),
                is_reversal=False
            )

            imported += 1

        session.last_sync = datetime.now()
        db.commit()

        return {
            "status": "imported",
            "imported": imported,
            "skipped": skipped,
            "total": len(parsed),
            "period": f"{date_from} → {date_to}"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
