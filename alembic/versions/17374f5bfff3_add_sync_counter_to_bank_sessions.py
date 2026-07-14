"""add_sync_counter_to_bank_sessions

Revision ID: 17374f5bfff3
Revises: 14eaedaa0494
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa

revision = '17374f5bfff3'
down_revision = '14eaedaa0494'
branch_labels = None
depends_on = None


def upgrade():
    # Licznik synchronizacji dziennych
    op.add_column('bank_sessions',
        sa.Column('sync_count_today', sa.Integer(), nullable=False, server_default='0')
    )
    # Data ostatniego resetu licznika
    op.add_column('bank_sessions',
        sa.Column('sync_count_date', sa.Date(), nullable=True)
    )


def downgrade():
    op.drop_column('bank_sessions', 'sync_count_date')
    op.drop_column('bank_sessions', 'sync_count_today')
