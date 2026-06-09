"""add_invite_system_and_roles

Revision ID: 73eb69313f21
Revises: 7df98a36a973
Create Date: 2026-06-09

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers
revision = '73eb69313f21'
down_revision = '7df98a36a973'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Dodaj kolumny do users
    op.add_column('users',
        sa.Column('role', sa.String(20), nullable=False, server_default='admin')
    )
    op.add_column('users',
        sa.Column('invited_by', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_users_invited_by', 'users', 'users',
        ['invited_by'], ['id'], ondelete='SET NULL'
    )

    # 2. Utwórz tabelę invitations
    op.create_table('invitations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],
                                ondelete='CASCADE')
    )

    # 3. Utwórz tabelę user_data_access
    op.create_table('user_data_access',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE')
    )

    # 4. Ustaw admina (user_id=2) jako admin
    op.execute("UPDATE users SET role = 'admin' WHERE id = 2")


def downgrade():
    op.drop_table('user_data_access')
    op.drop_table('invitations')
    op.drop_constraint('fk_users_invited_by', 'users', type_='foreignkey')
    op.drop_column('users', 'invited_by')
    op.drop_column('users', 'role')
