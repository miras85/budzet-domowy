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
    # Backfill istniejących wierszy do głównego właściciela (id=1),
    # tak jak w migracji BBAN. Zachowuje dotychczasowe okresy rozliczeniowe.
    op.execute("UPDATE payday_overrides SET user_id = 1 WHERE user_id IS NULL")
    op.create_foreign_key(
        'fk_payday_overrides_user_id', 'payday_overrides', 'users',
        ['user_id'], ['id']
    )


def downgrade():
    op.drop_constraint('fk_payday_overrides_user_id', 'payday_overrides', type_='foreignkey')
    op.drop_column('payday_overrides', 'user_id')
