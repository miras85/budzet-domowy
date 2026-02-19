# PROJECT CONTEXT – DomowyBudzet

## 1. Cel projektu

DomowyBudzet to prywatna aplikacja do zarządzania budżetem domowym,
tworzona jako PWA (Progressive Web App), działająca na urządzeniach mobilnych.

Projekt jest rozwijany głównie dla użytku własnego i rodziny,
z możliwością ewolucji w kierunku SaaS w przyszłości.

Priorytety:
- Intuicyjność użytkowania
- Szybkość działania
- Prosta, czytelna architektura kodu
- Łatwość utrzymania i rozwoju
- Długoterminowa skalowalność

Autor nie jest zawodowym programistą – kod musi być:
- jasny
- dobrze opisany
- łatwy do modyfikacji
- odporny na przypadkowe błędy przy edycji


---

## 2. Stack technologiczny

### Backend
- Python
- FastAPI
- SQLAlchemy
- MySQL (XAMPP lokalnie)
- Pydantic (schemas)
- Uvicorn

Serwer uruchamiany przez:
~/Library/LaunchAgents/com.domowybudzet.api.plist

Aplikacja dostępna z zewnątrz przez:
- Cloudflare Tunnel
- Własną domenę

---

### Frontend
- Vanilla JavaScript (modularna struktura)
- HTML + CSS
- PWA (manifest.json + service worker)
- Własny routing po stronie JS

Struktura:
- api.js (komunikacja z backendem)
- components/ (widoki)
- main.js (bootstrapping aplikacji)

---

## 3. Architektura backendu

Podział warstw:

- routers/ → warstwa HTTP
- services/ → logika biznesowa
- models.py → ORM
- schemas.py → walidacja danych
- database.py → konfiguracja DB

Założenie:
Logika biznesowa NIE powinna znajdować się w routerach.
Routery powinny jedynie:
- odbierać request
- wywoływać service
- zwracać response

---

## 4. Aktualny etap projektu

- Aplikacja działa
- Jest używana produkcyjnie (przez autora)
- Rozwijana iteracyjnie
- Brak testów automatycznych
- Brak systemu migracji (na razie)

---

## 5. Długoterminowa wizja

Etap 1 – narzędzie prywatne:
- stabilność
- czytelność kodu
- dobre UX

Etap 2 – potencjalny SaaS:
- multi-user
- multi-tenant
- bezpieczne auth
- skalowalna baza
- separacja konfiguracji
- testy
- migracje
- CI/CD

Architektura powinna być projektowana tak,
aby umożliwić przejście do etapu 2 bez przepisywania wszystkiego.

---

## 6. Zasady współpracy z agentem AI

1. Agent nie zakłada, że plik został wklejony w całości,
   dopóki autor tego nie potwierdzi.

2. Agent nie wprowadza zmian w kodzie,
   dopóki autor nie potwierdzi, że wszystkie pliki zostały przesłane.

3. Po potwierdzeniu:
   - agent może proponować ulepszenia
   - agent może proponować refaktoryzację proaktywnie
   - autor wyznacza kierunek rozwoju

4. Jeśli zmiany obejmują:
   - wiele miejsc w pliku → zwróć cały plik
   - pojedyncze miejsce → podaj dokładnie:
       - gdzie wkleić
       - co zastąpić
       - co usunąć

5. Kod musi być:
   - czytelny
   - zgodny z dobrymi praktykami
   - przyszłościowy (best long-term architecture)

6. Jeśli coś jest niejasne – agent zadaje pytania przed implementacją.

---

## 7. Filozofia rozwoju

- Najpierw dobra architektura, potem funkcje
- Małe kroki, częste refaktoryzacje
- Unikanie "quick hacków"
- Każda nowa funkcja:
    - powinna mieć wyraźne miejsce w architekturze
    - nie powinna łamać warstw
    - powinna być zgodna z wizją SaaS-ready

---

## 8. Styl kodu

Backend:
- logika w services
- routery cienkie
- brak duplikacji
- czytelne nazwy funkcji
- typowanie tam, gdzie możliwe

Frontend:
- podział na komponenty
- brak globalnego chaosu
- oddzielona komunikacja z API
- minimalna logika w HTML

---

## 9. Ograniczenia

- Autor wkleja pliki ręcznie (limit znaków)
- Agent nie ma pamięci między sesjami
- Kontekst projektu musi być zawsze aktualny na podstawie plików
