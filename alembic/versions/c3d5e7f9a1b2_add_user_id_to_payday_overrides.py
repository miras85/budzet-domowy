"""add_user_id_to_payday_overrides

Revision ID: c3d5e7f9a1b2
Revises: b7f2a1c9d3e4
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d5e7f9a1b2'
down_revision = 'b7f2a1c9d3e4'
branch_labels = None
depends_on = None


def upgrade():
    # Multi-tenancy: przypisujemy nadpisania dnia wypłaty do konkretnego
    # gospodarstwa (właściciela danych), aby nie były współdzielone globalnie.
    op.add_column('payday_overrides',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )
    # Backfill istniejących wierszy do głównego właściciela = najstarszy
    # użytkownik (najniższe id, czyli oryginalny admin). Odporne na to,
    # jakie realnie id ma admin. Zachowuje dotychczasowe okresy rozliczeniowe.
    op.execute(
        "UPDATE payday_overrides "
        "SET user_id = (SELECT id FROM users ORDER BY id ASC LIMIT 1) "
        "WHERE user_id IS NULL"
    )


def downgrade():
    op.drop_column('payday_overrides', 'user_id')
