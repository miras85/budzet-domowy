"""
Warstwowy silnik kategoryzacji transakcji (współdzielony przez import ING,
import CSV oraz uczenie z ręcznych operacji).

Kolejność dopasowania (od najpewniejszego):
  1. LEARNED   — wzorce nauczone z decyzji użytkownika (learned_patterns),
                 wybieramy kategorię o najwyższym hit_count.
  2. STATIC    — statyczna mapa znanych polskich sprzedawców -> koncept ->
                 pierwsza pasująca kategoria użytkownika (tylko wydatki).
  3. HISTORY   — dopasowanie po historii transakcji tego samego typu (ilike).
  4. None      — brak pewnego dopasowania.

Klucz dopasowania (merchant_token) jest ZAWSZE liczony przez
utils.pick_category_keyword (pomija słowa generyczne) i sprowadzany do lower.
Wszystko jest ściśle ograniczone do danych właściciela (user_id).
"""
from datetime import datetime
from sqlalchemy import func
import models
import utils


# --- STATYCZNA MAPA SPRZEDAWCÓW (Krok 2) ---
# token (lower) -> koncept. Token to wynik pick_category_keyword,
# więc np. "LIDL 2225 01 KRAKOW" -> "lidl".
STATIC_KEYWORD_MAP = {
    # spożywcze
    "biedronka": "groceries", "lidl": "groceries", "kaufland": "groceries",
    "auchan": "groceries", "carrefour": "groceries", "netto": "groceries",
    "żabka": "groceries", "zabka": "groceries", "dino": "groceries",
    "stokrotka": "groceries", "aldi": "groceries", "delikatesy": "groceries",
    "polomarket": "groceries", "intermarche": "groceries", "makro": "groceries",
    "spar": "groceries",
    # paliwo
    "orlen": "fuel", "shell": "fuel", "circle": "fuel", "lotos": "fuel",
    "amic": "fuel", "moya": "fuel", "lukoil": "fuel",
    # gastronomia
    "mcdonald": "eating_out", "mcdonalds": "eating_out", "kfc": "eating_out",
    "restauracja": "eating_out", "pizza": "eating_out", "pizzeria": "eating_out",
    "kebab": "eating_out", "sushi": "eating_out", "starbucks": "eating_out",
    # zdrowie / drogeria
    "apteka": "pharmacy", "rossmann": "pharmacy", "hebe": "pharmacy",
    "superpharm": "pharmacy",
    # transport
    "uber": "transport", "bolt": "transport", "kasownik": "transport",
    "intercity": "transport", "koleje": "transport",
    # subskrypcje / multimedia
    "netflix": "subscriptions", "spotify": "subscriptions", "disney": "subscriptions",
    "youtube": "subscriptions", "hbo": "subscriptions",
    # odzież
    "zalando": "clothing", "reserved": "clothing", "sinsay": "clothing",
    "zara": "clothing",
    # zakupy online / elektronika
    "allegro": "online_shopping", "amazon": "online_shopping",
    "instant": "online_shopping",
}

# koncept -> lista kandydatów na nazwę kategorii (po polsku, częste warianty).
# Bierzemy PIERWSZĄ nazwę, którą użytkownik faktycznie ma. Jeśli żadnej nie ma,
# warstwa statyczna "pudłuje" i schodzimy do historii — nic się nie psuje.
CONCEPT_CATEGORY_CANDIDATES = {
    "groceries": ["Zakupy spożywcze", "Spożywcze", "Żywność", "Jedzenie",
                  "Jedzenie i chemia", "Zakupy"],
    "fuel": ["Paliwo", "Samochód", "Auto", "Transport"],
    "eating_out": ["Restauracje", "Jedzenie na mieście", "Restauracja",
                   "Gastronomia", "Rozrywka", "Jedzenie"],
    "pharmacy": ["Zdrowie", "Apteka", "Drogeria", "Kosmetyki", "Leki"],
    "transport": ["Transport", "Komunikacja", "Podróże", "Samochód"],
    "subscriptions": ["Subskrypcje", "Multimedia", "Rozrywka", "Abonamenty"],
    "clothing": ["Odzież", "Ubrania", "Moda", "Zakupy"],
    "online_shopping": ["Zakupy online", "Zakupy", "Elektronika", "Dom"],
}


def _token(merchant_key=None, description=None):
    """Zwraca znormalizowany (lower) token sprzedawcy lub None."""
    kw = utils.pick_category_keyword(merchant_key) or \
         utils.pick_category_keyword(description)
    return kw.lower() if kw else None


def _learned_lookup(db, user_id: int, token: str):
    """Najczęstsza (max hit_count) nauczona kategoria dla tokenu; istniejąca u usera."""
    row = db.query(models.LearnedPattern).join(
        models.Category, models.LearnedPattern.category_id == models.Category.id
    ).filter(
        models.LearnedPattern.user_id == user_id,
        models.LearnedPattern.merchant_token == token,
        models.Category.user_id == user_id,
    ).order_by(
        models.LearnedPattern.hit_count.desc(),
        models.LearnedPattern.updated_at.desc(),
    ).first()
    return row.category_id if row else None


def _static_lookup(db, user_id: int, token: str):
    """Kategoria ze statycznej mapy — pierwsza nazwa kandydata, którą user ma."""
    concept = STATIC_KEYWORD_MAP.get(token)
    if not concept:
        return None
    for name in CONCEPT_CATEGORY_CANDIDATES.get(concept, []):
        cat = db.query(models.Category).filter(
            models.Category.user_id == user_id,
            func.lower(models.Category.name) == name.lower(),
        ).first()
        if cat:
            return cat.id
    return None


def _history_lookup(db, user_id: int, tx_type: str, token: str):
    """Dopasowanie po historii transakcji tego samego typu (user-scoped)."""
    row = db.query(models.Transaction).join(
        models.Account, models.Transaction.account_id == models.Account.id
    ).filter(
        models.Account.user_id == user_id,
        models.Transaction.category_id.isnot(None),
        models.Transaction.type == tx_type,
        models.Transaction.description.ilike(f"%{token}%"),
    ).order_by(models.Transaction.id.desc()).first()
    return row.category_id if row else None


def suggest_category(db, *, user_id: int, tx_type: str,
                     merchant_key: str = None, description: str = None):
    """
    Zwraca category_id (lub None) wg warstw: learned -> static -> history.
    Zawsze user-scoped. Transfery i brak danych -> None.
    """
    if not (db and user_id) or tx_type == "transfer":
        return None
    token = _token(merchant_key, description)
    if not token:
        return None

    cid = _learned_lookup(db, user_id, token)
    if cid:
        return cid

    if tx_type == "expense":
        cid = _static_lookup(db, user_id, token)
        if cid:
            return cid

    return _history_lookup(db, user_id, tx_type, token)


def learn_pattern(db, *, user_id: int, category_id: int,
                  merchant_key: str = None, description: str = None):
    """
    Uczy/wzmacnia wzorzec sprzedawca->kategoria na podstawie decyzji użytkownika.
    Nie commituje (robi to wywołujący). Błędy są łykane — uczenie nigdy nie może
    wywrócić zapisu transakcji.
    """
    try:
        if not (db and user_id and category_id):
            return
        token = _token(merchant_key, description)
        if not token:
            return
        row = db.query(models.LearnedPattern).filter(
            models.LearnedPattern.user_id == user_id,
            models.LearnedPattern.merchant_token == token,
            models.LearnedPattern.category_id == category_id,
        ).first()
        if row:
            row.hit_count = (row.hit_count or 0) + 1
            row.updated_at = datetime.utcnow()
        else:
            db.add(models.LearnedPattern(
                user_id=user_id,
                merchant_token=token,
                category_id=category_id,
                hit_count=1,
            ))
        db.flush()
        print(f"[LEARN] {token!r} -> kategoria {category_id} (user {user_id})")
    except Exception as e:
        print(f"[LEARN] pominięto uczenie wzorca: {e}")
