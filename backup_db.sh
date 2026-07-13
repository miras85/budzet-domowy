#!/bin/bash

# ═══════════════════════════════════════════════════════════
# DOMOWYBUDZET - Automatic Database Backup Script
# Auto SSH Tunnel + Local Mac Backup + Oracle Copy
# ═══════════════════════════════════════════════════════════

# Konfiguracja
BACKUP_DIR="$HOME/BudzetBackups"
DB_USER="domowybudzet"
DB_NAME="domowy_budzet"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${DATE}.sql"
LOG_FILE="$BACKUP_DIR/backup.log"

# SSH / Oracle konfiguracja
ORACLE_HOST="130.61.220.202"
ORACLE_USER="ubuntu"
SSH_KEY="$HOME/.ssh/oracle_homebudget"
LOCAL_PORT="3307"  # Używamy 3307 żeby nie kolidować z lokalnym MySQL

# Kolory
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Funkcja logowania
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo -e "$1"
}

# Funkcja czyszczenia (zamknij tunel)
cleanup() {
    if [ ! -z "$TUNNEL_PID" ]; then
        log "${YELLOW}🔌 Zamykam tunel SSH (PID: $TUNNEL_PID)${NC}"
        kill "$TUNNEL_PID" 2>/dev/null
    fi
}
trap cleanup EXIT

# ═══════════════════════════════════════════════
log "${GREEN}═══════════════════════════════════════════════${NC}"
log "${GREEN}🔄 Rozpoczynam backup bazy danych${NC}"
log "${GREEN}═══════════════════════════════════════════════${NC}"

# Sprawdź czy folder istnieje
if [ ! -d "$BACKUP_DIR" ]; then
    log "${YELLOW}📁 Tworzę folder backupów: $BACKUP_DIR${NC}"
    mkdir -p "$BACKUP_DIR"
fi

# ═══════════════════════════════════════════════
# KROK 1: Otwórz tunel SSH
# ═══════════════════════════════════════════════
log "🔌 Otwieram tunel SSH do Oracle..."

# Sprawdź czy port 3307 jest już zajęty
# Zawsze zabij stary tunel jeśli istnieje
if lsof -i :$LOCAL_PORT > /dev/null 2>&1; then
    log "${YELLOW}⚠️  Port $LOCAL_PORT zajęty — zamykam stary tunel${NC}"
    lsof -ti :$LOCAL_PORT | xargs kill -9 2>/dev/null
    sleep 2
fi

# Zawsze otwieraj nowy tunel
log "🔌 Otwieram nowy tunel SSH..."
ssh -i "$SSH_KEY" \
    -L ${LOCAL_PORT}:localhost:3306 \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=10 \
    -N -f \
    "$ORACLE_USER@$ORACLE_HOST"

TUNNEL_PID=$(lsof -t -i :$LOCAL_PORT)

if [ -z "$TUNNEL_PID" ]; then
    log "${RED}❌ Nie udało się otworzyć tunelu SSH!${NC}"
    exit 1
fi
log "${GREEN}✅ Tunel SSH aktywny (PID: $TUNNEL_PID)${NC}"

# Poczekaj chwilę na tunel
sleep 2

# ═══════════════════════════════════════════════
# KROK 2: Wykonaj backup
# ═══════════════════════════════════════════════
log "💾 Tworzę dump bazy: $DB_NAME"

/Applications/XAMPP/bin/mysqldump \
    --defaults-extra-file="$HOME/.my.cnf.backup" \
    --protocol=TCP \
    --host=127.0.0.1 \
    --port=$LOCAL_PORT \
    --no-tablespaces \
    "$DB_NAME" > "$BACKUP_FILE" 2>> "$LOG_FILE"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    LINES=$(wc -l < "$BACKUP_FILE")
    log "${GREEN}✅ Backup lokalny ukończony!${NC}"
    log "${GREEN}📦 Plik: $BACKUP_FILE${NC}"
    log "${GREEN}📦 Rozmiar: $BACKUP_SIZE | Linii: $LINES${NC}"
else
    log "${RED}❌ BŁĄD: Backup nie powiódł się!${NC}"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# ═══════════════════════════════════════════════
# KROK 3: Kopia na Oracle VM
# ═══════════════════════════════════════════════
log "☁️  Kopiuję backup na Oracle VM..."

scp -i "$SSH_KEY" \
    -o StrictHostKeyChecking=no \
    "$BACKUP_FILE" \
    "$ORACLE_USER@$ORACLE_HOST:~/BudzetBackups/"

if [ $? -eq 0 ]; then
    log "${GREEN}✅ Kopia na Oracle ukończona!${NC}"
else
    log "${YELLOW}⚠️  Kopia na Oracle nie powiodła się (backup lokalny OK)${NC}"
fi

# ═══════════════════════════════════════════════
# KROK 4: Usuń stare backupy (30 dni)
# ═══════════════════════════════════════════════
log "🧹 Usuwam backupy starsze niż 30 dni..."
find "$BACKUP_DIR" -name "backup_*.sql" -type f -mtime +30 -delete 2>> "$LOG_FILE"
REMAINING=$(find "$BACKUP_DIR" -name "backup_*.sql" | wc -l)
log "📁 Pozostałe backupy lokalne: $REMAINING"

# ═══════════════════════════════════════════════
log "${GREEN}═══════════════════════════════════════════════${NC}"
log "${GREEN}✅ Backup zakończony pomyślnie!${NC}"
log "${GREEN}   Mac:    $BACKUP_FILE${NC}"
log "${GREEN}   Oracle: ~/BudzetBackups/$(basename $BACKUP_FILE)${NC}"
log "${GREEN}═══════════════════════════════════════════════${NC}"
