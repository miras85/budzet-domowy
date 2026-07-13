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
    """
    Pobiera transakcje dla konta.
    date_from/date_to w formacie YYYY-MM-DD
    """
    headers = get_auth_headers()

    # Dodaj session header
    headers["X-Session-Id"] = session_id

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
    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd pobierania transakcji: {r.text}"
        )
    return r.json().get("transactions", [])


def get_session_accounts(session_id: str) -> list:
    """Pobiera listę kont z sesji"""
    headers = get_auth_headers()
    headers["X-Session-Id"] = session_id

    r = requests.get(f"{API_BASE}/sessions/{session_id}", headers=headers)
    if r.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd pobierania sesji: {r.text}"
        )
    return r.json().get("accounts", [])
