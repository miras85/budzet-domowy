"""add_enable_banking_uid_to_accounts

Revision ID: f3a5b7c9d1e2
Revises: e2f4a6b8c0d1
Create Date: 2026-07-23

Zapamiętuje Enable Banking uid konta, żeby przy imporcie nie wołać /details
ani /balances dla każdego konta osobno (endpoint /balances jest ostro
limitowany przez ING). Salda (dla blokad) pobieramy tylko dla konta z debetem
(RÓR) → 1 zapytanie o salda na import zamiast 3.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a5b7c9d1e2'
down_revision = 'e2f4a6b8c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('accounts',
        sa.Column('enable_banking_uid', sa.String(64), nullable=True)
    )


def downgrade():
    op.drop_column('accounts', 'enable_banking_uid')
