# services/banking.py
import jwt
import requests
import re
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
import os
import utils
from services import categorization

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
                     date_from: str = None, date_to: str = None,
                     transaction_status: str = None) -> list:
    """Pobiera transakcje konta z Enable Banking.

    transaction_status: pojedynczy status wg specyfikacji (np. 'BOOK' albo 'PDNG').
    UWAGA: parametr jest JEDNOWARTOŚCIOWY, a domyślnie API zwraca tylko 'BOOK'.
    Nie da się w jednym zapytaniu dostać booked+pending — pending (blokady)
    wymaga osobnego wywołania z transaction_status='PDNG'.
    """
    headers = get_auth_headers()

    params = {}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    if transaction_status:
        params["transaction_status"] = transaction_status

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


def get_account_details(account_uid: str) -> dict:
    """Pobiera szczegóły konta: GET /accounts/{uid}/details.

    Zwraca m.in.:
      - account_id: {iban}
      - all_account_ids: [{identification, scheme_name}]  (np. BBAN) → mapowanie
      - credit_limit: {currency, amount}  <-- LIMIT DEBETU (overdraft)
      - identification_hash

    credit_limit pozwala policzyć blokady bez ręcznej konfiguracji limitu:
    blokady = booked (ITBD) + credit_limit − available (ITAV).
    """
    headers = get_auth_headers()
    r = requests.get(
        f"{API_BASE}/accounts/{account_uid}/details",
        headers=headers,
    )
    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After")
        detail = (f"ING rate limit — poczekaj {int(retry_after) // 60}min "
                  f"{int(retry_after) % 60}s." if retry_after
                  else "ING chwilowo blokuje zapytania (rate limit).")
        raise HTTPException(status_code=429, detail=detail)
    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd pobierania szczegółów konta: {r.text}"
        )
    return r.json()


def get_balances(account_uid: str) -> list:
    """Pobiera salda konta z Enable Banking: GET /accounts/{uid}/balances.

    Zwraca listę obiektów salda (HalBalances.balances). Każdy element ma m.in.:
      - name
      - balance_amount: {currency, amount}
      - balance_type: kod z enuma (CLBD, CLAV, ITBD, ITAV, XPCD, FWAV, ...)
      - last_change_date_time / reference_date

    Wykorzystywane do wyliczenia "zablokowanych środków" (blokady kartowe ING
    nie są dostępne jako transakcje PDNG, widać je tylko w saldach:
    booked - available).
    """
    headers = get_auth_headers()
    r = requests.get(
        f"{API_BASE}/accounts/{account_uid}/balances",
        headers=headers,
    )

    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After")
        if retry_after:
            wait_seconds = int(retry_after)
            detail = f"ING rate limit — poczekaj {wait_seconds // 60}min {wait_seconds % 60}s."
        else:
            detail = "ING chwilowo blokuje zapytania (rate limit)."
        raise HTTPException(status_code=429, detail=detail)

    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd pobierania sald: {r.text}"
        )
    return r.json().get("balances", [])


# Priorytety wyboru salda "zaksięgowanego" i "dostępnego" spośród typów, które
# potrafi zwrócić ING. Nie wiemy z góry, który podzbiór przyśle dane konto,
# więc bierzemy pierwszy dostępny wg priorytetu (od najbardziej "śróddziennego").
#   booked (ile realnie zaksięgowano):  ITBD (interim) -> CLBD (closing) -> OPBD
#   available (ile mogę wydać po blokadach): ITAV -> CLAV -> XPCD (expected) -> FWAV
_BOOKED_PRIORITY = ["ITBD", "CLBD", "OPBD"]
_AVAILABLE_PRIORITY = ["ITAV", "CLAV", "XPCD", "FWAV"]


def _pick_balance(by_type: dict, priority: list):
    """Zwraca (typ, kwota) pierwszego dostępnego salda wg listy priorytetów."""
    for t in priority:
        if t in by_type:
            return t, by_type[t]
    return None, None


def compute_blocked_funds(balances: list):
    """Wylicza "zablokowane środki" = max(0, booked - available) z listy sald.

    Zwraca dict do zalogowania/kalibracji:
      {blocked, booked_type, booked, avail_type, available, all: {typ: kwota}}
    Blokada jest heurystyką: booked-available ≈ blokady kartowe, ale nie jest
    dokładne (debet/kredyt odnawialny, FX, opłaty, timing). Do pierwszej
    kalibracji logujemy WSZYSTKIE typy sald z kwotami.
    """
    by_type = {}
    for b in balances:
        t = b.get("balance_type")
        amt = (b.get("balance_amount") or {}).get("amount")
        if t is None or amt is None:
            continue
        try:
            by_type[t] = float(amt)
        except (TypeError, ValueError):
            continue

    booked_type, booked = _pick_balance(by_type, _BOOKED_PRIORITY)
    avail_type, available = _pick_balance(by_type, _AVAILABLE_PRIORITY)

    blocked = None
    if booked is not None and available is not None:
        blocked = max(0.0, round(booked - available, 2))

    return {
        "blocked": blocked,
        "booked_type": booked_type,
        "booked": booked,
        "avail_type": avail_type,
        "available": available,
        "all": by_type,
    }


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


def extract_merchant_key(tx: dict, tx_type: str):
    """
    Zwraca 'czysty' klucz sprzedawcy (wydatek) / nadawcy (przychód) do
    dopasowania kategorii. Priorytet:
      1) creditor.name / debtor.name — nazwa strukturalna z banku (najpewniejsza),
      2) fallback: pierwsza linia adresu (address_line[0]) obcięta do części
         przed pierwszym blokiem 2+ spacji — ING wstawia tam 'SKLEP<spacje>MIASTO',
         więc bierzemy sam początek (nazwę sklepu, bez miasta).
    Zwraca None dla transferów albo braku danych.
    """
    if tx_type == "transfer":
        return None
    party = (tx.get("creditor") if tx_type == "expense" else tx.get("debtor")) or {}

    name = (party.get("name") or "").strip()
    if name:
        return name

    lines = party.get("postal_address", {}).get("address_line", []) or []
    if lines:
        raw = (lines[0] or "").strip()
        head = re.split(r"\s{2,}", raw)[0].strip()
        return head or raw or None
    return None


def find_category_for(db, description: str, tx_type: str, user_id: int,
                      merchant_key: str = None):
    """
    Auto-kategoryzacja na podstawie historii — dopasowanie po słowie kluczowym
    z transakcji o tym samym typie. Zwraca category_id lub None.

    Jeśli podano merchant_key (strukturalna nazwa sprzedawcy z banku), używamy
    go jako źródła słowa kluczowego — jest pewniejszy niż zbudowany opis.
    W przeciwnym razie fallback na pierwsze sensowne słowo opisu.
    """
    if not (db and user_id) or tx_type == "transfer":
        return None
    from models import Transaction, Account
    keyword = utils.pick_category_keyword(merchant_key) or \
              utils.pick_category_keyword(description)
    if not keyword:
        return None
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

    merchant_key = extract_merchant_key(tx, tx_type)

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
    internal_side = None

    if db and user_id:
        debtor_account = get_account_by_bban(db, debtor_bban, user_id) if debtor_bban else None
        creditor_account = get_account_by_bban(db, creditor_bban, user_id) if creditor_bban else None

        if debtor_account and creditor_account:
            # Oba konta są nasze — to transfer wewnętrzny!
            # NIE odrzucamy tu strony CRDT na ślepo: jeśli druga strona (DBIT)
            # nie zostanie pobrana z API (np. drugie konto nie jest podłączone
            # przez PSD2), stracilibyśmy przelew. Oznaczamy stronę (DBIT/CRDT)
            # i parujemy dopiero na poziomie całej paczki (parse_ing_transactions),
            # gdzie CRDT usuwamy TYLKO gdy istnieje odpowiadająca strona DBIT.
            tx_type = "transfer"
            source_account_id = debtor_account.id
            target_account_id = creditor_account.id
            internal_side = indicator  # "DBIT" lub "CRDT"
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

    # LOG DIAGNOSTYCZNY: przejście pending->booked. ING NIE wystawia blokad
    # kartowych jako PDNG (potwierdzone: /transactions zwraca tylko BOOK).
    # Blokady widać wyłącznie w saldach (patrz get_balances/compute_blocked_funds),
    # dlatego nie logujemy już sygnatury pending.

    result = {
        "date": tx_date,
        "amount": amount,
        "description": description,
        "type": tx_type,
        "status": "zrealizowana",
        "account_id": source_account_id,
        "reference": tx.get("entry_reference", ""),
        # Warstwowa kategoryzacja: learned -> static -> history (patrz
        # services/categorization.suggest_category). merchant_key (nazwa
        # strukturalna z banku) ma priorytet nad zbudowanym opisem.
        "category_id": categorization.suggest_category(
            db, user_id=user_id, tx_type=tx_type,
            merchant_key=merchant_key, description=description,
        ),
    }

    if target_account_id:
        result["target_account_id"] = target_account_id

    if internal_side:
        result["_internal_side"] = internal_side

    return result


def parse_ing_transactions(transactions: list, default_account_id: int,
                           db=None, user_id: int = None) -> list:
    """Konwertuje listę transakcji ING i sortuje deterministycznie po (data,
    entry_reference), tak by kolejność w obrębie dnia = kolejność bankowa."""
    result = []
    for tx in transactions:
        try:
            parsed = parse_ing_transaction(tx, default_account_id, db, user_id)
            if parsed is not None:
                result.append(parsed)
        except Exception as e:
            print(f"⚠️ Błąd parsowania transakcji: {e}")
            continue

    # Sparuj strony transferów wewnętrznych. Każdy przelew między naszymi kontami
    # może pojawić się dwukrotnie: jako DBIT (wychodzący z konta źródłowego) i CRDT
    # (przychodzący na docelowe). Jeśli mamy stronę DBIT, pomijamy odpowiadającą jej
    # stronę CRDT (ta sama para kont + kwota). Jeśli strony DBIT NIE ma (drugie konto
    # nie było pobrane z API), zachowujemy CRDT — inaczej zgubilibyśmy przelew.
    dbit_keys = set()
    for p in result:
        if p.get("_internal_side") == "DBIT":
            dbit_keys.add((p.get("account_id"), p.get("target_account_id"),
                           round(float(p.get("amount") or 0), 2)))

    deduped = []
    for p in result:
        if p.get("_internal_side") == "CRDT":
            key = (p.get("account_id"), p.get("target_account_id"),
                   round(float(p.get("amount") or 0), 2))
            if key in dbit_keys:
                print(f"[PARSE] Pomijam stronę CRDT transferu (jest DBIT): "
                      f"{p.get('account_id')}->{p.get('target_account_id')} "
                      f"{p.get('amount')} {p.get('description', '')[:40]!r}")
                continue  # jest strona DBIT — pomiń duplikat CRDT
            print(f"[PARSE] Zachowuję stronę CRDT transferu (brak DBIT w paczce): "
                  f"{p.get('account_id')}->{p.get('target_account_id')} "
                  f"{p.get('amount')} {p.get('description', '')[:40]!r}")
        p.pop("_internal_side", None)
        deduped.append(p)
    result = deduped

    # Kolejność w obrębie dnia jest istotna. NIE polegamy na kolejności zwracania
    # przez ING (bywa różna, a przy scalaniu wielu kont zależy od kolejności pętli),
    # tylko sortujemy DETERMINISTYCZNIE po (data, entry_reference).
    # entry_reference ma postać 'D202607130000001' = 'D' + RRRRMMDD + dzienny numer
    # sekwencyjny per konto. Rosnący entry_reference = kolejność nadana przez bank,
    # więc rosnący sort daje kolejność bankową w obrębie dnia. Kolejność wstawiania
    # do bazy (rosnące id) odwzorowuje wtedy kolejność bankową. Fallback do "" gdy
    # brak reference — takie trafiają na początek dnia, ale deterministycznie.
    result.sort(key=lambda x: (x.get("date") or "", x.get("reference") or ""))
    return result

