# Oracle Cloud Migration - Notes

## Data migracji: 2026-02-24

---

## OBECNA KONFIGURACJA (Mac):

### Backend:
- Lokalizacja: ~/HomeBudget
- Port: 8000
- Process manager: LaunchAgent (com.domowybudzet.api.plist)
- Python version: Python 3.9.6
- Logi: /tmp/domowybudzet_api*.log

### MySQL:
- User: domowybudzet
- Password: DomBudz3t!Secur3_2026
- Database: domowy_budzet
- Port: 3306
- Location: XAMPP

### Cloudflare Tunnel:
- Domain: budzet-domowy.pl
- Target: http://localhost:8000
- Tunnel ID: N/A (działa)

### Dane do migracji:

**Liczba rekordów (przed migracją):**
+----------+--------------+-------+------------+-------+
| accounts | transactions | goals | categories | loans |
+----------+--------------+-------+------------+-------+
|        4 |         1011 |     8 |         23 |    10 |
+----------+--------------+-------+------------+-------+

Backup file: /Users/mireksniezek/BudzetBackups/backup_20260225_084550.sql 
Backup size: [116K]

ORACLE CLOUD:
Account Name: Home 
Region: Germany Central (Frankfurt) 
Tenancy: miroslawsniezek
Username: miroslaw.sniezek@gmail.com
 
KONFIGURACJA PO MIGRACJI (będzie wypełnione):
Oracle VM:
•	Public IP: _______________
•	SSH user: ubuntu
•	SSH key: ~/.ssh/oracle_homebudget
MySQL (Oracle):
•	User: domowybudzet (ten sam)
•	Password: DomBudz3t!Secur3_2026
•	Database: domowy_budzet
•	Port: 3306
Backend (Oracle):
•	Location: /home/ubuntu/homebudget
•	systemd service: homebudget.service
•	Logi: /var/log/homebudget/
Nginx:
•	Config: /etc/nginx/sites-available/homebudget
•	Proxy: localhost:8000


