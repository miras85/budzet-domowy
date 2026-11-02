#!/bin/bash
# ═══════════════════════════════════════════════════════════
# DOMOWYBUDZET - Automatyczny import transakcji z ING (cron)
# Uruchamiany lokalnie na Oracle o 6:00 czasu polskiego
# (crontab: 0 6 * * *, serwer w TZ Europe/Warsaw).
# Woła DOKŁADNIE ten sam endpoint co ręczny import w UI
# (/api/banking/import), więc status importu (last_sync,
# sync_count_today/4) aktualizuje się identycznie jak przy
# ręcznym kliknięciu "Importuj z ING".
#
# AUTO-NADRABIANIE LUKI: zamiast sztywnego okna 7 dni, zakres
# importu liczony jest od MIN(data ostatniego udanego importu,
# dziś−7) — jeśli poprzednie uruchomienia padały (np. wygasła
# sesja banku / CLOSED_SESSION), pierwszy udany import po
# naprawie sam nadrobi całą zaległość, bez ręcznego wpisywania
# dat. Zabezpieczenie: nie cofamy się dalej niż 90 dni (przy
# dłuższej przerwie potrzebny jest ręczny import z szerszym
# zakresem — patrz procedura odzyskiwania w dokumentacji).
# ═══════════════════════════════════════════════════════════
set -euo pipefail

API="http://127.0.0.1:8000"
ENV_FILE="/home/ubuntu/homebudget/.auto_import_env"   # chmod 600, poza gitem
LOG="/var/log/homebudget/auto_import.log"
MAX_LOOKBACK_DAYS=90

ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [ ! -f "$ENV_FILE" ]; then
    echo "[$(ts)] BŁĄD: brak pliku $ENV_FILE (dane logowania)" >> "$LOG"
    exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

TOKEN=$(curl -s -X POST "${API}/token" \
    --data-urlencode "username=${AUTO_IMPORT_USER}" \
    --data-urlencode "password=${AUTO_IMPORT_PASS}" \
    | python3 -c 'import sys,json
try:
    print(json.load(sys.stdin).get("access_token",""))
except Exception:
    print("")')

if [ -z "$TOKEN" ]; then
    echo "[$(ts)] BŁĄD: logowanie nieudane (sprawdź AUTO_IMPORT_USER/PASS w ${ENV_FILE})" >> "$LOG"
    exit 1
fi

# --- Ustal zakres importu: auto-nadrabianie luki ---
TODAY=$(date '+%Y-%m-%d')
WINDOW_7D=$(date -d '7 days ago' '+%Y-%m-%d')
LOOKBACK_LIMIT=$(date -d "${MAX_LOOKBACK_DAYS} days ago" '+%Y-%m-%d')

STATUS_JSON=$(curl -s "${API}/api/banking/status" -H "Authorization: Bearer ${TOKEN}")
LAST_SYNC_RAW=$(echo "${STATUS_JSON}" | python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
    print(d.get("last_sync") or "")
except Exception:
    print("")')

if [ -n "$LAST_SYNC_RAW" ]; then
    LAST_SYNC_DATE="${LAST_SYNC_RAW:0:10}"
    # MIN(data ostatniego udanego importu, dziś−7) — wcześniejsza data wygrywa,
    # bo oznacza większą zaległość do nadrobienia. Porównanie leksykograficzne
    # dziala poprawnie dla formatu YYYY-MM-DD.
    if [[ "$LAST_SYNC_DATE" < "$WINDOW_7D" ]]; then
        DATE_FROM="$LAST_SYNC_DATE"
        GAP_INFO="luka wykryta (ostatni udany import: ${LAST_SYNC_DATE}) - nadrabiam"
    else
        DATE_FROM="$WINDOW_7D"
        GAP_INFO="brak luki (ostatni udany import: ${LAST_SYNC_DATE})"
    fi
    # Zabezpieczenie: nie cofaj sie dalej niz MAX_LOOKBACK_DAYS
    if [[ "$DATE_FROM" < "$LOOKBACK_LIMIT" ]]; then
        DATE_FROM="$LOOKBACK_LIMIT"
        GAP_INFO="${GAP_INFO} (przyciete do limitu ${MAX_LOOKBACK_DAYS} dni)"
    fi
else
    DATE_FROM="$WINDOW_7D"
    GAP_INFO="brak danych o ostatnim imporcie - domyslne okno 7 dni"
fi
DATE_TO="$TODAY"

echo "[$(ts)] START auto-import ${DATE_FROM} -> ${DATE_TO} (${GAP_INFO})" >> "$LOG"

RESP=$(curl -s -X POST \
    "${API}/api/banking/import?date_from=${DATE_FROM}&date_to=${DATE_TO}" \
    -H "Authorization: Bearer ${TOKEN}")

echo "[$(ts)] Odpowiedź: ${RESP}" >> "$LOG"
echo "[$(ts)] KONIEC" >> "$LOG"
