# PROJECT_CONTEXT.md

## 1. Opis aplikacji i cel

**DomowyBudzet** to prywatna aplikacja PWA (Progressive Web App) do zarządzania budżetem domowym dla pojedynczego gospodarstwa domowego. Aplikacja służy do:

- Śledzenia przychodów i wydatków
- Zarządzania wieloma kontami bankowymi
- Planowania i realizacji celów oszczędnościowych
- Monitorowania kredytów i rat
- Zarządzania subskrypcjami i płatnościami cyklicznymi
- Importu transakcji z plików CSV banków
- Analizy wydatków z wykresami i statystykami

**Kontekst użycia:**
- Single-user → Shared household (wspólny budżet dla dwóch osób)
- Dane finansowe prywatne, nie planowany public SaaS
- Prywatny hosting + Cloudflare

---

## 2. Aktualne funkcje

### Zarządzanie transakcjami:
- Dodawanie transakcji (przychód/wydatek/transfer)
- Statusy: "zrealizowana" / "planowana"
- Edycja i usuwanie transakcji
- Auto-kategoryzacja na podstawie historii
- Import CSV z banków (ING, inne formaty)
- Wyszukiwanie i filtrowanie transakcji

### Konta:
- Wielokontowe (ROR + oszczędnościowe)
- Śledzenie sald (aktualizowane automatycznie)
- Rozróżnienie kont oszczędnościowych (do celów)

### Cele oszczędnościowe:
- Tworzenie celów z deadline
- Zasilanie celów (transfer z ROR → oszczędności)
- Obliczanie wymaganej kwoty miesięcznej ("monthly_need")
- Wypłata z celów
- Transfer między celami

### Kredyty i zobowiązania:
- Śledzenie kredytów i rat
- Automatyczne przesunięcie daty płatności
- Kategoryzacja spłat jako "Spłata zobowiązań"

### Płatności cykliczne (Subskrypcje):
- Definiowanie powtarzalnych opłat
- Automatyczne przypomnienia (popup przy logowaniu)
- Dodawanie jako "planowana" lub pomijanie

### Analizy i raporty:
- Dashboard z kluczowymi metrykami
- Cykle rozliczeniowe (25-go dnia miesiąca, z nadpisaniami)
- Wykresy trendów (6 miesięcy wstecz)
- Wykres kołowy wydatków (doughnut chart)
- Budżety miesięczne dla kategorii
- Wskaźnik stopy oszczędności

### Kategorie:
- Własne kategorie z custom ikonami i kolorami
- Limity miesięczne dla kategorii
- Wizualizacja przekroczenia limitów

### Inne:
- PWA (działa offline, instalowalna)
- Autentykacja JWT (login/logout)
- Multi-user (możliwość dodania domownika)
- Zmiana hasła

---

## 3. Struktura frontendu

### Technologie:
- **Vue 3** (CDN: `vue@3/dist/vue.esm-browser.js`)
- **Tailwind CSS** (CDN, wersja runtime)
- **Chart.js** (do wykresów)
- **Service Worker** (PWA offline support)

### Architektura:

static/
├── index.html (Single-page app)
├── app.js (Legacy, obecnie nieużywane)
├── style.css (Custom styles + Tailwind overrides)
├── sw.js (Service Worker, cache v7)
├── manifest.json (PWA manifest)
│
└── js/
    ├── main.js (Entry point, Vue app initialization)
    ├── api.js (HTTP client, wszystkie API calls)
    ├── utils.js (Helpery: formatMoney, formatDate, etc.)
    ├── charts.js (Chart.js wrappers)
    ├── icons.js (SVG paths dla custom ikon kategorii)
    │
    └── components/
        ├── LoginView.js
        ├── DashboardView.js (3 tryby: lista/kategorie/wykresy)
        ├── AccountsView.js
        ├── GoalsView.js
        ├── PaymentsView.js (kredyty + subskrypcje)
        ├── SettingsView.js (kategorie, payday overrides, bezpieczeństwo)
        ├── AddTransactionView.js
        ├── SearchView.js
        ├── ImportModal.js
        └── TheNavigation.js (bottom navigation bar)

### Kluczowe mechanizmy:
- **Reactive data** w głównym Vue instance (`main.js`)
- **Props/Emits** między komponentami (unidirectional data flow)
- **Computed properties** do filtrowania i grupowania danych
- **Toast notifications** (auto-ukrywanie po 4s)
- **Gesty mobilne** (swipe left/right dla zmiany okresów)

---

## 4. Struktura backendu

### Technologie:
- **FastAPI** (Python 3)
- **SQLAlchemy** (ORM)
- **MySQL** (via XAMPP lokalnie)
- **JWT** (jose + passlib/bcrypt)
- **Pydantic** (walidacja schemas)

### Architektura:

DomowyBudzet/
├── main.py (FastAPI app, startup events)
├── database.py (Engine, SessionLocal, get_db, get_current_user)
├── auth.py (JWT creation, password hashing)
├── models.py (SQLAlchemy models)
├── schemas.py (Pydantic DTOs)
├── utils.py (Logika dat, update_balance, update_loan_balance)
│
├── routers/
│   ├── auth.py (/token, /api/users, /api/users/change-password)
│   ├── finance.py (transactions, accounts, goals, loans, categories, import)
│   └── recurring.py (/api/recurring/*)
│
└── services/
    ├── transaction.py (CRUD transakcji, search)
    ├── dashboard.py (dashboard data, trend data)
    ├── goal.py (fund, withdraw, transfer)
    └── bank_import.py (parse CSV, save imported)

### Warstwy:
1. **Routers** – FastAPI endpoints (routing, auth, basic validation)
2. **Services** – Business logic (transakcje, obliczenia, transformacje)
3. **Models** – SQLAlchemy ORM (tabele, relacje)
4. **Utils** – Helpery (daty, salda, logika cykli rozliczeniowych)

---

## 5. API

### Autentykacja:
- `POST /token` – Login (OAuth2 PasswordRequestForm)
- `POST /api/users` – Rejestracja nowego użytkownika (wymaga auth)
- `POST /api/users/change-password` – Zmiana hasła

### Finanse:
- `GET /api/dashboard?offset={int}` – Dashboard data dla cyklu rozliczeniowego
- `GET /api/stats/trend` – Dane do wykresu trendów (6 miesięcy)
- `POST /api/transactions` – Dodaj transakcję
- `PUT /api/transactions/{id}` – Edytuj transakcję
- `DELETE /api/transactions/{id}` – Usuń transakcję
- `GET /api/transactions/search?{params}` – Wyszukiwanie

### Konta:
- `GET /api/accounts` – Lista kont
- `POST /api/accounts` – Utwórz konto
- `PUT /api/accounts/{id}` – Edytuj konto
- `DELETE /api/accounts/{id}` – Usuń konto

### Cele:
- `GET /api/goals` – Lista celów
- `POST /api/goals` – Utwórz cel
- `POST /api/goals/{id}/fund` – Zasil cel
- `POST /api/goals/{id}/withdraw` – Wypłać z celu
- `POST /api/goals/{id}/transfer` – Transfer między celami
- `DELETE /api/goals/{id}` – Usuń cel

### Kredyty:
- `GET /api/loans` – Lista kredytów
- `POST /api/loans` – Dodaj kredyt
- `PUT /api/loans/{id}` – Edytuj kredyt

### Płatności cykliczne:
- `GET /api/recurring` – Lista subskrypcji
- `GET /api/recurring/check` – Sprawdź wymagalne płatności
- `POST /api/recurring` – Dodaj subskrypcję
- `POST /api/recurring/{id}/process` – Wykonaj płatność
- `POST /api/recurring/{id}/skip` – Pomiń płatność
- `DELETE /api/recurring/{id}` – Usuń subskrypcję

### Kategorie:
- `GET /api/categories` – Lista kategorii
- `POST /api/categories` – Dodaj kategorię (z ikoną/kolorem)
- `PUT /api/categories/{id}` – Edytuj kategorię
- `DELETE /api/categories/{id}` – Usuń kategorię

### Import:
- `POST /api/import/preview` – Parse CSV, zwróć preview
- `POST /api/import/confirm` – Zapisz zaimportowane transakcje

### Ustawienia:
- `GET /api/settings/payday-overrides` – Lista nadpisań daty wypłaty
- `POST /api/settings/payday-overrides` – Dodaj nadpisanie
- `DELETE /api/settings/payday-overrides/{id}` – Usuń nadpisanie

### Auth:
- **Bearer token** w header `Authorization: Bearer {token}`
- Auto-logout przy 401

---

## 6. Model danych

### Tabele:

#### User
- `id` (PK)
- `username` (unique)
- `hashed_password`

#### Account
- `id` (PK)
- `name`
- `type` (string: "bank", "cash", etc.)
- `balance` (DECIMAL)
- `is_savings` (boolean) – czy konto oszczędnościowe

#### Transaction
- `id` (PK)
- `amount` (DECIMAL)
- `description`
- `date`
- `type` ("income", "expense", "transfer")
- `status` ("zrealizowana", "planowana")
- `account_id` (FK → Account)
- `target_account_id` (FK → Account, nullable)
- `category_id` (FK → Category, nullable)
- `loan_id` (FK → Loan, nullable)

#### Category
- `id` (PK)
- `name` (unique)
- `monthly_limit` (DECIMAL)
- `icon_name` (string: klucz do ikony SVG)
- `color` (string: hex color)

#### Loan
- `id` (PK)
- `name`
- `total_amount` (DECIMAL)
- `remaining_amount` (DECIMAL)
- `monthly_payment` (DECIMAL)
- `next_payment_date` (Date)

#### Goal
- `id` (PK)
- `name`
- `target_amount` (DECIMAL)
- `current_amount` (DECIMAL)
- `deadline` (Date)
- `is_archived` (boolean)
- `account_id` (FK → Account) – konto oszczędnościowe

#### GoalContribution
- `id` (PK)
- `goal_id` (FK → Goal)
- `amount` (DECIMAL, może być ujemna przy wypłacie)
- `date` (Date)

#### RecurringTransaction
- `id` (PK)
- `name`
- `amount` (DECIMAL)
- `day_of_month` (Integer)
- `last_run_date` (Date, nullable)
- `is_active` (boolean)
- `category_id` (FK → Category, nullable)
- `account_id` (FK → Account, nullable)

#### PaydayOverride
- `id` (PK)
- `year` (Integer)
- `month` (Integer)
- `day` (Integer)

### Relacje:
- Transaction → Account (many-to-one)
- Transaction → Category (many-to-one)
- Transaction → Loan (many-to-one)
- Goal → Account (many-to-one)
- GoalContribution → Goal (many-to-one)
- RecurringTransaction → Category, Account (many-to-one)

### Brak relacji user_id:
Wszystkie tabele (poza User) **NIE MAJĄ** `user_id` – aplikacja single-household.

### Migracje:
**Brak systemu migracji** (Alembic, etc.)
- Tabele tworzone przez `models.Base.metadata.create_all(bind=engine)` w `main.py`
- Zmiany w modelach wymagają ręcznej interwencji

---

## 7. Bezpieczeństwo

### Mechanizmy obecne:

**Autentykacja:**
- JWT tokens (jose library)
- Hasła hashowane bcrypt (passlib)
- Token w header `Authorization: Bearer {token}`

**Walidacja:**
- Pydantic schemas po stronie API
- Vue validations po stronie UI (wybór konta, kategoria przy imporcie)

**.gitignore:**
- `.env` nie trafia do repozytorium

### Kluczowe braki i ryzyka:

**KRYTYCZNE:**

1. **Token w localStorage (XSS vector)**
   - Lokalizacja: `api.js: localStorage.setItem('token', newToken)`
   - Ryzyko: XSS attack → kradzież tokenu → pełny dostęp przez 30 dni
   - Fix: httpOnly cookie + CSRF token (wymaga backend)

2. **SECRET_KEY słaby**
   - Wartość: `"zmien_mnie_na_bardzo_dlugi_losowy_ciag_znakow_dla_bezpieczenstwa_123456"`
   - Fix: `openssl rand -hex 32` → wklej do `.env`

3. **MySQL root bez hasła**
   - Wartość: `root:@localhost`
   - Fix: Ustaw hasło lub stwórz dedykowanego usera

4. **Token ważny 30 dni**
   - `ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30`
   - Brak refresh token mechanism
   - Fix: Skróć do 7 dni + implementuj refresh token

5. **Brak rate-limiting**
   - Endpoint `/token` bez ochrony brute-force
   - Fix: slowapi lub middleware FastAPI

6. **Brak CSP headers**
   - Aplikacja podatna na XSS
   - Fix: Dodać `Content-Security-Policy` w FastAPI middleware

7. **Tailwind/Chart.js z CDN**
   - Nie działa offline (mimo SW)
   - CDN może być skompromitowany
   - Fix: Build-time Tailwind + lokalny Chart.js

**WYSOKIE:**

8. **Brak transakcji SQL (multi-step operations)**
   - Przykład: `transaction.update_transaction()` – 4 kroki bez atomicity
   - Ryzyko: Częściowe wykonanie = niespójne salda
   - Fix: `db.begin()` / `try-except-rollback` w serwisach

9. **Auto-commit kategorii w środku operacji**
   - `db.commit()` w `create_transaction()` przed zakończeniem głównej operacji
   - Fix: Usunąć intermediate commits, jeden commit na końcu

10. **Konwersja DECIMAL → float**
    - `val = float(amount)` w `utils.py`
    - Ryzyko: Błędy zaokrągleń w finansach
    - Fix: Używać `Decimal` z `decimal` library przez całą aplikację

11. **Brak deduplikacji importu CSV**
    - Można zaimportować te same transakcje wielokrotnie
    - Fix: Check (date, amount, description) before insert

12. **Logout nie czyści stanu aplikacji**
    - `this.dashboard`, `this.accounts` pozostają w pamięci Vue
    - Fix: Reset wszystkich reactive data do defaults

**ŚREDNIE:**

13. **Brak walidacji kwot (backend)**
    - Schemas akceptują `float` bez `min`/`max`
    - Fix: Pydantic `Field(gt=0)` dla amount

14. **Brak soft-delete**
    - `DELETE` usuwa fizycznie (brak audytu)
    - Fix: Flaga `is_deleted` + filtrowanie w queries

15. **Częściowy import bez rollback**
    - Przy błędzie zapisuje ile się udało
    - Fix: Transakcja SQL dla całego importu

---

## 8. Ryzyka architektoniczne (priorytetyzacja)

### P0 (Napraw natychmiast przed produkcją):

| # | Ryzyko | Lokalizacja | Skutek | Fix Effort |
|---|--------|-------------|--------|------------|
| 1 | Token w localStorage | api.js | Kradzież przez XSS → pełny dostęp | HIGH (zmiana backend + frontend) |
| 2 | SECRET_KEY słaby | .env | Podrobienie tokenów JWT | LOW (1 min) |
| 3 | MySQL root bez hasła | .env | Dostęp do bazy z innych procesów | LOW (5 min) |
| 4 | Brak transakcji SQL | services/*.py | Niespójne salda przy błędach | MEDIUM (refactor serwisów) |
| 5 | Tailwind CDN | index.html | Nie działa offline w pełni | MEDIUM (setup build) |

### P1 (Napraw przed skalowaniem):

| # | Ryzyko | Lokalizacja | Skutek | Fix Effort |
|---|--------|-------------|--------|------------|
| 6 | Rate-limiting | routers/auth.py | Brute-force | LOW (middleware) |
| 7 | DECIMAL→float | utils.py | Błędy zaokrągleń | MEDIUM (zmiana typów) |
| 8 | Deduplikacja importu | bank_import.py | Duplikaty transakcji | LOW (hash check) |
| 9 | CSP headers | Backend | XSS | LOW (middleware) |

### P2 (Nice-to-have / Optymalizacje):

| # | Ryzyko | Lokalizacja | Skutek | Fix Effort |
|---|--------|-------------|--------|------------|
| 10 | Soft-delete | finance.py | Brak audytu | MEDIUM |
| 11 | Częste refetche | main.js | Wolne UX | LOW (optymalizacja) |
| 12 | Brak testów | Cały projekt | Trudne utrzymanie | HIGH |

---

## 9. Gotowość pod SaaS

### Co blokuje SaaS:

**Brak user_id w modelach danych**
- Wszystkie tabele (Account, Transaction, Goal, etc.) nie mają relacji do User
- Wymagane: Migracja dodająca `user_id` + backfill dla istniejących rekordów

**Brak systemu migracji bazy**
- `create_all()` nie obsługuje zmian schematu
- Wymagane: Alembic + historia migracji

**Single-secret dla wszystkich użytkowników**
- Jeden SECRET_KEY dla całej aplikacji
- Wymagane: Per-user session management lub różne klucze

**Brak limitów zasobów (quotas)**
- Użytkownik może stworzyć nieskończoną liczbę transakcji/kont
- Wymagane: Limity per user/plan

### Co pomaga:

- Modularność backendu (Services layer = łatwe dodanie multi-tenancy logic)
- JWT authentication (łatwo rozszerzyć o role user/admin)
- PWA architecture (dobrze skaluje się na różne urządzenia)
- API-first design (Frontend całkowicie oddzielony od backend)

---

## 10. TODO / Propozycje ulepszeń

### Quick Wins (1-2h pracy każda):

1. Zmień SECRET_KEY na silny losowy (`openssl rand -hex 32`)
2. Ustaw hasło MySQL lub stwórz dedykowanego usera
3. Dodaj rate-limiting na `/token` (slowapi)
4. Fix formatMoney NaN – dodaj fallback `|| 0`
5. Clear state on logout – reset `this.dashboard` etc.

### Short-term (1 tydzień):

6. Refactor transakcji SQL – wrap w `db.begin()` / `try-except-rollback`
7. Deduplikacja importu – hash check (date+amount+desc)
8. CSP headers – FastAPI middleware
9. Walidacja kwot – Pydantic `Field(gt=0)`
10. Build Tailwind – PostCSS + purge

### Medium-term (1 miesiąc):

11. Migracja DECIMAL – zmień `float()` na `Decimal()` w całym projekcie
12. Alembic – system migracji bazy
13. Soft-delete – flaga `is_deleted` zamiast fizycznego usuwania
14. Unit testy – pytest dla serwisów
15. Token refresh mechanism – refresh token + short-lived access token

### Long-term (3+ miesiące, jeśli SaaS):

16. Multi-tenancy – dodanie `user_id` do wszystkich tabel + migracja
17. Quotas/Limits – limity per user
18. Billing – integracja Stripe/PayPal
19. Admin panel – zarządzanie userami
20. Monitoring – Sentry + logs

---

## 11. Wydajność

### Obecne bottlenecks:

**Dashboard z wieloma celami:**
- Dla każdego celu: pętla `while` (max 120 iteracji) + query `func.sum(GoalContribution)`
- Fix: Cache wyników `get_billing_period()`, optymalizacja SQL

**Częste pełne odświeżenia:**
- Po każdej operacji: `fetchData()` + `fetchAccounts()` (2 requesty)
- Fix: Optymistic UI updates + background sync

**Brak paginacji:**
- `GET /api/transactions/search` zwraca wszystkie wyniki
- Fix: Pagination (offset/limit) dla dużych wyników

### Optymalizacje zaimplementowane:

- Chart instances destroy – przed re-render
- Computed properties – cache filteredTransactions, groupedCategories
- Service Worker – cache plików statycznych

---

## 12. Deployment

### Aktualna konfiguracja:

- **Backend:** Python/FastAPI (uruchamianie przez macOS LaunchAgents)
- **Baza:** MySQL (XAMPP lokalnie)
- **Frontend:** Pliki statyczne w `/static`
- **Produkcja:** Cloudflare + domena
- **Tunel:** `cloudflared` (widoczny w project manifest)

### Deployment flow (przewidywany):

1. LaunchAgent uruchamia FastAPI app (`main.py`)
2. Cloudflare Tunnel (`cloudflared`) mapuje publiczną domenę → localhost
3. Frontend serwowany przez FastAPI (`/static`)
4. PWA cache'uje pliki przez Service Worker

### Ryzyka deploymentu:

**Brak process managera:**
- LaunchAgent może nie zrestartować przy crash
- Fix: Dodaj `KeepAlive=true` w plist + monitoring

**Brak backup bazy:**
- MySQL bez automated backups
- Fix: Cron job + mysqldump

**Secrets w .env:**
- `.env` na serwerze produkcyjnym (OK jeśli tylko Ty masz dostęp)
- Lepiej: Environment variables systemowe

---

## 13. Użyte biblioteki i zależności

### Backend (Python):
fastapi
uvicorn
sqlalchemy
mysqlconnector
python-jose[cryptography]  # JWT
passlib[bcrypt]            # Hashing haseł
python-multipart           # File uploads
pydantic                   # Validation
python-dotenv              # .env loading

### Frontend (CDN):
Vue 3 (vue@3/dist/vue.esm-browser.js)
Tailwind CSS (cdn.tailwindcss.com)
Chart.js (cdn.jsdelivr.net/npm/chart.js)

### Dev Dependencies (widoczne w requirements.txt):
beautifulsoup4, extract-msg, olefile, oletools  # Parsowanie dokumentów (nieużywane?)
cryptography, ecdsa, pyasn1, rsa               # Crypto (zależności jose)

---

## 14. Wersjonowanie i Git

### Strategia:

- Xcode jako Git client (macOS)
- `.gitignore` zawiera: `__pycache__/`, `*.pyc`, `.env`, `venv/`
- Brak widocznych branchy/tags w plikach

### Ryzyka:

**Brak .env.example:**
- Nowy deweloper nie wie jakie zmienne są wymagane
- Fix: Dodaj `.env.example` z placeholderami

**Brak CHANGELOG.md:**
- Trudno śledzić zmiany między wersjami
- Fix: Konwencja Semantic Versioning + changelog

---

## 15. Kluczowe pliki do modyfikacji przy zmianach

### Dodawanie nowego feature:

1. **Model danych:** `models.py` (nowa tabela)
2. **Schema:** `schemas.py` (DTO dla API)
3. **Service:** `services/{new_feature}.py` (logika biznesowa)
4. **Router:** `routers/finance.py` lub nowy plik
5. **API client:** `js/api.js` (nowa funkcja w odpowiedniej sekcji)
6. **Component:** `js/components/{NewView}.js`
7. **Main:** `js/main.js` (dodanie metod i data properties)

### Zmiana logiki biznesowej:

- **Salda:** `utils.py` (`update_balance`, `update_loan_balance`)
- **Daty:** `utils.py` (`get_billing_period`, `get_actual_payday`)
- **Dashboard:** `services/dashboard.py`

### Zmiana UI:

- **Style:** `style.css` (Tailwind overrides)
- **Komponenty:** `js/components/*.js`
- **Ikony kategorii:** `js/icons.js`

---

## 16. Znane bugi i ograniczenia

### Bugi:

1. Refresh po edycji transakcji resetuje filter (viewMode wraca do 'list')
2. Import CSV z pustą kolumną Amount – może crashnąć parser
3. Kategoria "Bez kategorii" nie ma limitu – nie jest w bazie

### Ograniczenia:

1. Brak historii zmian transakcji – nie wiadomo kto/kiedy edytował
2. Goal monthly_need obliczane synchronicznie (wolne przy 10+ celach)
3. Brak notyfikacji push – tylko popup przy logowaniu (recurring)
4. Brak eksportu danych (CSV, PDF)
5. Brak dark/light mode toggle (hardcoded dark)

---

Struktura URL:

    / → index.html (Vue app)
    /api/* → FastAPI endpoints
    /static/* → Pliki statyczne
    /token → OAuth2 login


Testowanie:

Brak testów w projekcie.

---

## HISTORIA ZMIAN

### 2026-02-19 - Wdrożenie Planu A (Minimum Bezpieczeństwa)

**Wykonane:**
1. ✅ SECRET_KEY zmieniony na 64-znakowy losowy (openssl rand -hex 32)
2. ✅ MySQL: utworzono dedykowanego usera `domowybudzet` (zamiast root bez hasła)
3. ✅ Logout czyści reactive data (prywatność)
4. ✅ formatMoney() obsługuje null/undefined (nie pokazuje "NaN zł")
5. ✅ Rate limiting na /token: max 5 prób/minutę z jednego IP

**Status bezpieczeństwa:** 
- Przed: 🔴 Krytyczne luki (token do podrobienia, brak ochrony brute-force)
- Po: ✅ Podstawowe zabezpieczenia wdrożone, aplikacja gotowa do użytku produkcyjnego

**Pozostałe do rozważenia (opcjonalnie):**
- Plan B: CSP headers, deduplikacja importu, transakcje SQL
- Plan C: Alembic, build Tailwind, DECIMAL precision
