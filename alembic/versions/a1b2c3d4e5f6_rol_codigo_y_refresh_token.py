"""Rol.codigo y tabla refresh_token

Revision ID: a1b2c3d4e5f6
Revises: 6dbcded228a4
Create Date: 2026-08-30 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6dbcded228a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rol', sa.Column('codigo', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_rol_codigo'), 'rol', ['codigo'], unique=True)

    op.create_table(
        'refresh_token',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expira_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revocado', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_refresh_token_usuario_id'), 'refresh_token', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_refresh_token_token_hash'), 'refresh_token', ['token_hash'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_refresh_token_token_hash'), table_name='refresh_token')
    op.drop_index(op.f('ix_refresh_token_usuario_id'), table_name='refresh_token')
    op.drop_table('refresh_token')
    op.drop_index(op.f('ix_rol_codigo'), table_name='rol')
    op.drop_column('rol', 'codigo')
