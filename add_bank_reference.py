"""
Migracja: dodaje kolumnę transactions.bank_reference (unikalny identyfikator
transakcji z banku - entry_reference) używaną do niezawodnej deduplikacji importu.

Uruchom JEDNORAZOWO na Oracle po pull:
    python add_bank_reference.py
"""
from sqlalchemy import text
from database import engine


def run():
    with engine.connect() as conn:
        exists = conn.execute(text(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'transactions'
              AND COLUMN_NAME = 'bank_reference'
            """
        )).scalar()

        if exists:
            print("ℹ️  Kolumna bank_reference już istnieje — pomijam.")
            return

        conn.execute(text(
            "ALTER TABLE transactions ADD COLUMN bank_reference VARCHAR(255) NULL"
        ))
        conn.execute(text(
            "CREATE INDEX ix_transactions_bank_reference ON transactions (bank_reference)"
        ))
        conn.commit()
        print("✅ Dodano kolumnę bank_reference + indeks.")


if __name__ == "__main__":
    run()
