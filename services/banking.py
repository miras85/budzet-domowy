# services/banking.py
import jwt
import requests
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
import os

# Konfiguracja Enable Banking
APP_ID = os.getenv("ENABLE_BANKING_APP_ID", "1c02300f-053a-4c23-88ea-01144af2521d")
PEM_PATH = os.getenv("ENABLE_BANKING_PEM_PATH", "/home/ubuntu/homebudget/1c02300f-053a-4c23-88ea-01144af2521d.pem")
API_BASE = "https://api.enablebanking.com"
REDIRECT_URL = os.getenv("ENABLE_BANKING_REDIRECT_URL", "https://budzet-domowy.pl/api/banking/callback")


def get_auth_headers() -> dict:
    """Generuje JWT token i zwraca headers do API"""
    try:
        private_key = open(PEM_PATH, "rb").read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Brak pliku klucza Enable Banking")

    iat = int(datetime.now().timestamp())
    token = jwt.encode(
        {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": iat,
            "exp": iat + 3600
        },
        private_key,
        algorithm="RS256",
        headers={"kid": APP_ID}
    )
    return {"Authorization": f"Bearer {token}"}


def get_available_banks(country: str = "PL") -> list:
    """Pobiera listę dostępnych banków"""
    headers = get_auth_headers()
    r = requests.get(f"{API_BASE}/aspsps?country={country}", headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Błąd pobierania listy banków")
    return r.json().get("aspsps", [])


def start_bank_auth(bank_name: str, bank_country: str = "PL") -> str:
    """
    Rozpoczyna autoryzację z bankiem.
    Zwraca URL do którego należy przekierować użytkownika.
    """
    headers = get_auth_headers()
    body = {
        "access": {
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        },
        "aspsp": {
            "name": bank_name,
            "country": bank_country
        },
        "state": f"user-auth-{int(datetime.now().timestamp())}",
        "redirect_url": REDIRECT_URL,
        "psu_type": "personal"
    }
    r = requests.post(f"{API_BASE}/auth", json=body, headers=headers)
    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd autoryzacji banku: {r.text}"
        )
    return r.json().get("url")


def create_session(code: str) -> dict:
    """
    Tworzy sesję po powrocie z banku.
    Zwraca session_id i listę kont.
    """
    headers = get_auth_headers()
    r = requests.post(f"{API_BASE}/sessions", json={"code": code}, headers=headers)
    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd tworzenia sesji: {r.text}"
        )
    return r.json()


def get_transactions(session_id: str, account_uid: str,
                     date_from: str = None, date_to: str = None) -> list:
    headers = get_auth_headers()

    params = {}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    r = requests.get(
        f"{API_BASE}/accounts/{account_uid}/transactions",
        headers=headers,
        params=params
    )

    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After")
        if retry_after:
            wait_seconds = int(retry_after)
            minutes = wait_seconds // 60
            seconds = wait_seconds % 60
            detail = f"ING rate limit — poczekaj {minutes}min {seconds}s przed kolejnym zapytaniem."
        else:
            detail = "ING chwilowo blokuje zapytania (rate limit). Poczekaj kilka minut i spróbuj ponownie."
        raise HTTPException(status_code=429, detail=detail)

    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd pobierania transakcji: {r.text}"
        )
    return r.json().get("transactions", [])


def get_session_accounts(session_id: str) -> list:
    """Pobiera listę kont z sesji"""
    headers = get_auth_headers()

    r = requests.get(f"{API_BASE}/sessions/{session_id}", headers=headers)
    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd pobierania sesji: {r.text}"
        )
    data = r.json()
    # ING zwraca konta w accounts_data z polem uid
    accounts_data = data.get("accounts_data", [])
    return [{"uid": acc["uid"]} for acc in accounts_data if "uid" in acc]

def get_account_by_bban(db, bban: str, user_id: int):
    """Znajdź konto po numerze BBAN"""
    if not bban:
        return None
    # Sprawdź czy bban zawiera się w numerze konta lub odwrotnie
    from models import Account
    accounts = db.query(Account).filter(
        Account.user_id == user_id
    ).all()
    for acc in accounts:
        if acc.bban and (
            acc.bban == bban or
            acc.bban.endswith(bban[-8:]) or
            bban.endswith(acc.bban[-8:])
        ):
            return acc
    return None


def parse_ing_transaction(tx: dict, default_account_id: int,
                          db=None, user_id: int = None) -> dict:
    """
    Konwertuje transakcję z formatu Enable Banking/ING
    na format DomowyBudżet.
    Wykrywa transfery wewnętrzne na podstawie BBAN.
    """
    amount = float(tx.get("transaction_amount", {}).get("amount", 0))
    indicator = tx.get("credit_debit_indicator", "DBIT")
    tx_type = "expense" if indicator == "DBIT" else "income"

    # Pobierz BBAN kont
    debtor_bban = None
    creditor_bban = None

    debtor_acc = tx.get("debtor_account", {})
    if debtor_acc:
        debtor_bban = debtor_acc.get("other", {}).get("identification") or \
                      debtor_acc.get("iban")

    creditor_acc = tx.get("creditor_account", {})
    if creditor_acc:
        creditor_bban = creditor_acc.get("other", {}).get("identification") or \
                        creditor_acc.get("iban")

    # Wykryj transfer wewnętrzny
    source_account_id = default_account_id
    target_account_id = None

    if db and user_id:
        debtor_account = get_account_by_bban(db, debtor_bban, user_id) if debtor_bban else None
        creditor_account = get_account_by_bban(db, creditor_bban, user_id) if creditor_bban else None

        if debtor_account and creditor_account:
            # Oba konta są nasze — to transfer wewnętrzny!
            # Importuj TYLKO stronę DBIT (wydatek z konta źródłowego)
            if indicator != "DBIT":
                return None  # Pomiń stronę CRDT — zapobiega duplikatom
            tx_type = "transfer"
            source_account_id = debtor_account.id
            target_account_id = creditor_account.id
        elif debtor_account and tx_type == "expense":
            source_account_id = debtor_account.id
        elif creditor_account and tx_type == "income":
            source_account_id = creditor_account.id

    # Opis transakcji
    remittance = tx.get("remittance_information", [])
    description_parts = []

    if tx_type == "transfer":
        # Dla transferów — opis z remittance
        if remittance:
            description_parts.append(remittance[0])
    elif tx_type == "expense":
        creditor = tx.get("creditor", {})
        address_lines = creditor.get("postal_address", {}).get("address_line", [])
        if address_lines:
            description_parts.append(address_lines[0].strip())
        if remittance:
            description_parts.append(remittance[0])
    else:
        debtor = tx.get("debtor", {})
        address_lines = debtor.get("postal_address", {}).get("address_line", [])
        if address_lines:
            description_parts.append(address_lines[0].strip())
        if remittance:
            description_parts.append(remittance[0])

    description = " | ".join(filter(None, description_parts))
    if not description:
        description = f"Transakcja ING {tx.get('booking_date', '')}"

    result = {
        "date": tx.get("booking_date"),
        "amount": amount,
        "description": description,
        "type": tx_type,
        "status": "zrealizowana",
        "account_id": source_account_id,
        "reference": tx.get("entry_reference", ""),
    }

    if target_account_id:
        result["target_account_id"] = target_account_id

    return result


def parse_ing_transactions(transactions: list, default_account_id: int,
                           db=None, user_id: int = None) -> list:
    """Konwertuje listę transakcji ING"""
    result = []
    for tx in transactions:
        try:
            parsed = parse_ing_transaction(tx, default_account_id, db, user_id)
            if parsed is not None:  # Pomiń CRDT strony transferów wewnętrznych
                result.append(parsed)
        except Exception as e:
            print(f"⚠️ Błąd parsowania transakcji: {e}")
            continue
    return result

