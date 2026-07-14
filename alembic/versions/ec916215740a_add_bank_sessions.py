"""add_bank_sessions

Revision ID: ec916215740a
Revises: 73eb69313f21
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa

revision = 'ec916215740a'
down_revision = '73eb69313f21'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('bank_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('bank_name', sa.String(100), nullable=False),
        sa.Column('bank_country', sa.String(10), nullable=False, server_default='PL'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('last_sync', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )


def downgrade():
    op.drop_table('bank_sessions')
