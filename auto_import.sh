#!/bin/bash
# ═══════════════════════════════════════════════════════════
# DOMOWYBUDZET - Automatyczny import transakcji z ING (cron)
# Uruchamiany lokalnie na Oracle o 3:00 (crontab: 0 3 * * *).
# Woła DOKŁADNIE ten sam endpoint co ręczny import w UI
# (/api/banking/import), więc status importu (last_sync,
# sync_count_today/4) aktualizuje się identycznie jak przy
# ręcznym kliknięciu "Importuj z ING".
# ═══════════════════════════════════════════════════════════
set -euo pipefail

API="http://127.0.0.1:8000"
ENV_FILE="/home/ubuntu/homebudget/.auto_import_env"   # chmod 600, poza gitem
LOG="/var/log/homebudget/auto_import.log"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [ ! -f "$ENV_FILE" ]; then
    echo "[$(ts)] BŁĄD: brak pliku $ENV_FILE (dane logowania)" >> "$LOG"
    exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

DATE_FROM=$(date -d '7 days ago' '+%Y-%m-%d')
DATE_TO=$(date '+%Y-%m-%d')

echo "[$(ts)] START auto-import ${DATE_FROM} -> ${DATE_TO}" >> "$LOG"

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

RESP=$(curl -s -X POST \
    "${API}/api/banking/import?date_from=${DATE_FROM}&date_to=${DATE_TO}" \
    -H "Authorization: Bearer ${TOKEN}")

echo "[$(ts)] Odpowiedź: ${RESP}" >> "$LOG"
echo "[$(ts)] KONIEC" >> "$LOG"
