"""add_overdraft_limit_and_blocked_funds_to_accounts

Revision ID: e2f4a6b8c0d1
Revises: d1a2b3c4e5f6
Create Date: 2026-07-22

Dodaje konfigurację limitu debetu (overdraft_limit) i migawkę zablokowanych
środków (blocked_funds) na kontach. ING nie wystawia limitu debetu przez API
(credit_limit=None), dlatego ustawiamy go ręcznie dla RÓR (2500 zł).
Blokady liczymy: blocked = ITBD + overdraft_limit − ITAV.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e2f4a6b8c0d1'
down_revision = 'd1a2b3c4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('accounts',
        sa.Column('overdraft_limit', sa.DECIMAL(10, 2), nullable=True, server_default='0.0')
    )
    op.add_column('accounts',
        sa.Column('blocked_funds', sa.DECIMAL(10, 2), nullable=True, server_default='0.0')
    )
    # Limit debetu RÓR (konto bieżące, bban ...9064903116). Reszta kont = 0.
    op.execute(
        "UPDATE accounts SET overdraft_limit = 2500 "
        "WHERE bban = '54105014451000009064903116'"
    )


def downgrade():
    op.drop_column('accounts', 'blocked_funds')
    op.drop_column('accounts', 'overdraft_limit')
