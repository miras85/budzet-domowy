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

# Mapowanie ostatnich 4 cyfr numeru karty -> właściciel (dopisywany do opisu)
CARD_OWNERS = {
    "9820": "Kasia",
    "5831": "Mirek",
}


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


def _extract_date_from_text(text: str):
    """
    Wyciąga datę w formacie DD.MM.YYYY / DD-MM-YYYY / DD/MM/YYYY z tekstu
    (np. z tytułu 'PŁATNOŚĆ KARTĄ 04.07.2026 ...'). Zwraca 'YYYY-MM-DD' lub None.
    """
    import re
    from datetime import date as _date
    if not text:
        return None
    m = re.search(r'(\d{2})[.\-/](\d{2})[.\-/](\d{4})', text)
    if not m:
        return None
    try:
        return _date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def detect_card_owner(text: str):
    """
    Rozpoznaje właściciela karty po ostatnich 4 cyfrach numeru karty w tytule
    płatności kartą (np. '... 9820 ...'). Zwraca imię lub None.
    Wymaga kontekstu 'kart' i dopasowuje 4 cyfry jako osobny token
    (nie fragment dłuższej liczby, np. numeru referencyjnego).
    """
    import re
    if not text or "kart" not in text.lower():
        return None
    for suffix, name in CARD_OWNERS.items():
        if re.search(rf'(?<!\d){suffix}(?!\d)', text):
            return name
    return None


def find_category_for(db, description: str, tx_type: str, user_id: int):
    """
    Auto-kategoryzacja na podstawie historii — dopasowanie po słowie kluczowym
    (pierwsze słowo > 3 znaki) z transakcji o tym samym typie. Zwraca category_id lub None.
    """
    if not (db and user_id and description) or tx_type == "transfer":
        return None
    import re
    from models import Transaction, Account
    words = [w for w in re.split(r"\s+", description) if len(w) > 3]
    if not words:
        return None
    keyword = words[0]
    similar = db.query(Transaction).join(
        Account, Transaction.account_id == Account.id
    ).filter(
        Account.user_id == user_id,
        Transaction.category_id.isnot(None),
        Transaction.type == tx_type,
        Transaction.description.ilike(f"%{keyword}%")
    ).order_by(Transaction.id.desc()).first()
    return similar.category_id if similar else None


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

    # Data transakcji. ING często księguje płatności kartą (zwł. weekendowe)
    # na kolejny dzień roboczy, więc booking_date bywa mylące.
    # Priorytet:
    #  1) data z tytułu płatności kartą ('PŁATNOŚĆ KARTĄ DD.MM.YYYY') — realna data zakupu
    #  2) transaction_date z API
    #  3) value_date z API
    #  4) booking_date z API
    api_date = tx.get("transaction_date") or tx.get("value_date") or tx.get("booking_date")

    desc_text = " ".join([p for p in description_parts if p])
    card_date = None
    if "kart" in desc_text.lower():
        card_date = _extract_date_from_text(desc_text)

    tx_date = card_date or api_date

    print(f"[PARSE] booking={tx.get('booking_date')} value={tx.get('value_date')} "
          f"transaction={tx.get('transaction_date')} card_title={card_date} status={tx.get('status')} "
          f"-> data={tx_date} ref={tx.get('entry_reference')!r} "
          f"kwota={amount} typ={tx_type}")

    description = " | ".join(filter(None, description_parts))
    if not description:
        description = f"Transakcja ING {tx_date or ''}"

    # Dopisz właściciela karty w nawiasie na podstawie ostatnich 4 cyfr numeru karty.
    # Szukamy w pełnym tekście (opis + wszystkie linie remittance), bo numer karty
    # może być w innej linii niż zbudowany opis.
    search_text = " ".join(filter(None, description_parts + [str(r) for r in remittance]))
    card_owner = detect_card_owner(search_text)
    if card_owner:
        description = f"{description} ({card_owner})"

    result = {
        "date": tx_date,
        "amount": amount,
        "description": description,
        "type": tx_type,
        "status": "zrealizowana",
        "account_id": source_account_id,
        "reference": tx.get("entry_reference", ""),
        "category_id": find_category_for(db, description, tx_type, user_id),
    }

    if target_account_id:
        result["target_account_id"] = target_account_id

    return result


def parse_ing_transactions(transactions: list, default_account_id: int,
                           db=None, user_id: int = None) -> list:
    """Konwertuje listę transakcji ING (posortowane chronologicznie: od najstarszej)"""
    result = []
    for tx in transactions:
        try:
            parsed = parse_ing_transaction(tx, default_account_id, db, user_id)
            if parsed is not None:  # Pomiń CRDT strony transferów wewnętrznych
                result.append(parsed)
        except Exception as e:
            print(f"⚠️ Błąd parsowania transakcji: {e}")
            continue

    # ING zwraca transakcje od najnowszej. Odwracamy (→ najstarsza pierwsza),
    # a następnie STABILNIE sortujemy rosnąco po dacie. Stabilny sort zachowuje
    # kolejność wewnątrz tego samego dnia (najstarsza pierwsza). Dzięki temu
    # kolejność wstawiania do bazy (rosnące id) = kolejność chronologiczna.
    result.reverse()
    result.sort(key=lambda x: (x.get("date") or ""))
    return result

