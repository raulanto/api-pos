"""producto_imagen: soporte de almacenamiento propio en S3

Una fila de `producto_imagen` ahora puede tener:
- `url` externa (como hasta ahora), o
- `object_key` + `content_type`: el binario vive en el bucket S3 y la URL
  pública se deriva prefirmada al leer. Por eso `url` pasa a ser nullable.

La key de la miniatura (la genera una Lambda) se deriva de `object_key` y no se
persiste.

Revision ID: b3d4e5f6a7c8
Revises: a1c2e3f4b5d6
Create Date: 2026-09-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3d4e5f6a7c8"
down_revision: Union[str, Sequence[str], None] = "a1c2e3f4b5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "producto_imagen", sa.Column("object_key", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "producto_imagen", sa.Column("content_type", sa.String(length=100), nullable=True)
    )
    op.alter_column("producto_imagen", "url", existing_type=sa.String(length=500), nullable=True)
    op.create_index(
        "ix_producto_imagen_object_key", "producto_imagen", ["object_key"]
    )


def downgrade() -> None:
    op.drop_index("ix_producto_imagen_object_key", table_name="producto_imagen")
    # Filas sin `url` (imágenes S3) romperían el NOT NULL: se descartan.
    op.execute("DELETE FROM producto_imagen WHERE url IS NULL")
    op.alter_column("producto_imagen", "url", existing_type=sa.String(length=500), nullable=False)
    op.drop_column("producto_imagen", "content_type")
    op.drop_column("producto_imagen", "object_key")
