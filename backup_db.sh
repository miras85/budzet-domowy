#!/bin/bash

# ═══════════════════════════════════════════════════════════
# DOMOWYBUDZET - Automatic Database Backup Script
# ═══════════════════════════════════════════════════════════

# Konfiguracja
BACKUP_DIR="$HOME/BudzetBackups"
DB_USER="domowybudzet"
DB_NAME="domowy_budzet"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${DATE}.sql"
LOG_FILE="$BACKUP_DIR/backup.log"

# Kolory dla output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funkcja logowania
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo -e "$1"
}

# Start
log "${GREEN}═══════════════════════════════════════════════${NC}"
log "${GREEN}🔄 Rozpoczynam backup bazy danych${NC}"
log "${GREEN}═══════════════════════════════════════════════${NC}"

# Sprawdź czy folder istnieje
if [ ! -d "$BACKUP_DIR" ]; then
    log "${YELLOW}📁 Tworzę folder backupów: $BACKUP_DIR${NC}"
    mkdir -p "$BACKUP_DIR"
fi

# Wykonaj mysqldump
log "💾 Tworzę dump bazy: $DB_NAME"

# Prompt o hasło (dla ręcznego uruchomienia)
# W crontab użyj: mysql_config_editor set --login-path=backup --user=domowybudzet --password
/Applications/XAMPP/bin/mysqldump --defaults-extra-file="$HOME/.my.cnf.backup" "$DB_NAME" > "$BACKUP_FILE" 2>> "$LOG_FILE"

# Sprawdź czy się udało
if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "${GREEN}✅ Backup ukończony: $BACKUP_FILE${NC}"
    log "${GREEN}📦 Rozmiar: $BACKUP_SIZE${NC}"
    
    # Policz liczbę rekordów (weryfikacja)
    LINES=$(wc -l < "$BACKUP_FILE")
    log "📊 Linii w pliku: $LINES"
    
else
    log "${RED}❌ BŁĄD: Backup nie powiódł się!${NC}"
    exit 1
fi

# Usuń backupy starsze niż 30 dni
log "🧹 Usuwam backupy starsze niż 30 dni..."
find "$BACKUP_DIR" -name "backup_*.sql" -type f -mtime +30 -delete 2>> "$LOG_FILE"

REMAINING=$(find "$BACKUP_DIR" -name "backup_*.sql" | wc -l)
log "📁 Pozostałe backupy: $REMAINING"

# Podsumowanie
log "${GREEN}═══════════════════════════════════════════════${NC}"
log "${GREEN}✅ Backup zakończony pomyślnie${NC}"
log "${GREEN}═══════════════════════════════════════════════${NC}"

echo ""
echo "Backup zapisany: $BACKUP_FILE"
echo "Log: $LOG_FILE"
