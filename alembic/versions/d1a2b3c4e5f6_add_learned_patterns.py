"""add_learned_patterns

Revision ID: d1a2b3c4e5f6
Revises: c3d5e7f9a1b2
Create Date: 2026-07-21

Tabela nauczonych wzorców sprzedawca -> kategoria (per użytkownik).
Migracja jest IDEMPOTENTNA, bo main.py wywołuje create_all na starcie i może
utworzyć tabelę zanim alembic dobije do tej rewizji. Dlatego przed utworzeniem
sprawdzamy inspektorem, czy tabela/indeksy już istnieją.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1a2b3c4e5f6'
down_revision = 'c3d5e7f9a1b2'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'learned_patterns' not in tables:
        op.create_table(
            'learned_patterns',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('merchant_token', sa.String(length=100), nullable=False),
            sa.Column('category_id', sa.Integer(), nullable=False),
            sa.Column('hit_count', sa.Integer(), nullable=False,
                      server_default='1'),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'merchant_token', 'category_id',
                                name='uq_learned_user_token_cat'),
        )

    # Indeksy sprawdzamy osobno — tabela mogła powstać przez create_all,
    # które i tak stworzy oba (PK index + jawny). Guard chroni przed dublem.
    existing_indexes = {ix['name'] for ix in inspector.get_indexes('learned_patterns')} \
        if 'learned_patterns' in inspector.get_table_names() else set()

    if 'ix_learned_patterns_lookup' not in existing_indexes:
        op.create_index('ix_learned_patterns_lookup', 'learned_patterns',
                        ['user_id', 'merchant_token'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'learned_patterns' in inspector.get_table_names():
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('learned_patterns')}
        if 'ix_learned_patterns_lookup' in existing_indexes:
            op.drop_index('ix_learned_patterns_lookup', table_name='learned_patterns')
        op.drop_table('learned_patterns')
