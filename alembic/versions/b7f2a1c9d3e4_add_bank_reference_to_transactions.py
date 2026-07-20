"""add_bank_reference_to_transactions

Revision ID: b7f2a1c9d3e4
Revises: 17374f5bfff3
Create Date: 2026-07-20

"""
from alembic import op
import sqlalchemy as sa

revision = 'b7f2a1c9d3e4'
down_revision = '17374f5bfff3'
branch_labels = None
depends_on = None


def upgrade():
    # Unikalny identyfikator transakcji z banku (entry_reference)
    # używany do niezawodnej, idempotentnej deduplikacji importu ING
    op.add_column('transactions',
        sa.Column('bank_reference', sa.String(length=255), nullable=True)
    )
    op.create_index(
        'ix_transactions_bank_reference', 'transactions', ['bank_reference']
    )


def downgrade():
    op.drop_index('ix_transactions_bank_reference', table_name='transactions')
    op.drop_column('transactions', 'bank_reference')
