"""agregar_marca_y_marca_id_a_producto

Revision ID: a0d89b8b3d31
Revises: 26c7b5276ac9
Create Date: 2026-10-01 18:58:44.164455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a0d89b8b3d31'
down_revision: Union[str, Sequence[str], None] = '26c7b5276ac9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('marca',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('producto', sa.Column('marca_id', sa.UUID(), nullable=True))
    op.create_foreign_key(None, 'producto', 'marca', ['marca_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'producto', type_='foreignkey')
    op.drop_column('producto', 'marca_id')
    op.drop_table('marca')

