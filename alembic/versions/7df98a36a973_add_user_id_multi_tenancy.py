"""add_user_id_multi_tenancy

Revision ID: 7df98a36a973
Revises: 313c49b974a6
Create Date: 2026-06-05

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '7df98a36a973'
down_revision = '313c49b974a6'
branch_labels = None
depends_on = None


def upgrade():
    # 1. ACCOUNTS
    op.add_column('accounts',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_accounts_user_id', 'accounts', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # 2. CATEGORIES
    op.add_column('categories',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_categories_user_id', 'categories', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # 3. LOANS
    op.add_column('loans',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_loans_user_id', 'loans', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # 4. GOALS
    op.add_column('goals',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_goals_user_id', 'goals', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # 5. RECURRING TRANSACTIONS
    op.add_column('recurring_transactions',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_recurring_user_id', 'recurring_transactions', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # 6. PRZYPISZ ISTNIEJĄCE DANE DO ADMINA (user_id=2)
    op.execute("UPDATE accounts SET user_id = 2")
    op.execute("UPDATE categories SET user_id = 2")
    op.execute("UPDATE loans SET user_id = 2")
    op.execute("UPDATE goals SET user_id = 2")
    op.execute("UPDATE recurring_transactions SET user_id = 2")

    # 7. USTAW NOT NULL po wypełnieniu danych
    op.alter_column('accounts', 'user_id',
        existing_type=sa.Integer(), nullable=False)
    op.alter_column('categories', 'user_id',
        existing_type=sa.Integer(), nullable=False)
    op.alter_column('loans', 'user_id',
        existing_type=sa.Integer(), nullable=False)
    op.alter_column('goals', 'user_id',
        existing_type=sa.Integer(), nullable=False)
    op.alter_column('recurring_transactions', 'user_id',
        existing_type=sa.Integer(), nullable=False)


def downgrade():
    # Usuń FK i kolumny w odwrotnej kolejności
    op.drop_constraint('fk_recurring_user_id',
        'recurring_transactions', type_='foreignkey')
    op.drop_column('recurring_transactions', 'user_id')

    op.drop_constraint('fk_goals_user_id',
        'goals', type_='foreignkey')
    op.drop_column('goals', 'user_id')

    op.drop_constraint('fk_loans_user_id',
        'loans', type_='foreignkey')
    op.drop_column('loans', 'user_id')

    op.drop_constraint('fk_categories_user_id',
        'categories', type_='foreignkey')
    op.drop_column('categories', 'user_id')

    op.drop_constraint('fk_accounts_user_id',
        'accounts', type_='foreignkey')
    op.drop_column('accounts', 'user_id')
