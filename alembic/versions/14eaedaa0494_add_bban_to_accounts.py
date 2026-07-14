"""add_bban_to_accounts

Revision ID: 14eaedaa0494
Revises: ec916215740a
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa

revision = '14eaedaa0494'
down_revision = 'ec916215740a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('accounts',
        sa.Column('bban', sa.String(50), nullable=True)
    )
    # ROR
    op.execute("UPDATE accounts SET bban = '54105014451000009064903116' WHERE id = 1")
    # Podróże
    op.execute("UPDATE accounts SET bban = '47105014581000002296106442' WHERE id = 2")
    # Fundusz domowy
    op.execute("UPDATE accounts SET bban = '77105014451000009740430005' WHERE id = 3")


def downgrade():
    op.drop_column('accounts', 'bban')
