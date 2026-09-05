import uuid
from sqlalchemy import (
    Column, String, SmallInteger, Boolean, ForeignKey, CheckConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base, TimestampMixin

"""
    Tabla: producto_imagen
    Descripcion: Galería de imágenes. El dueño es EXACTAMENTE uno de los dos:
        `producto_id` (producto simple o kit) o `producto_unidad_id`
        (presentación de venta, p. ej. la unidad suelta de un fraccionable).
    Columnas:
    - id
    - producto_id: FK a producto.id (nullable)
    - producto_unidad_id: FK a producto_unidad.id (nullable)
    - url: URL de la imagen
    - alt_texto: descripción / texto alternativo
    - orden: posición en la galería
    - es_principal: miniatura/portada del dueño
    - created_at, updated_at

    Restricciones:
    - ck_producto_imagen_un_solo_dueno: exactamente uno de los dos FK está seteado.

    Indices:
    - ix_producto_imagen_producto / ix_producto_imagen_producto_unidad: listar
      la galería de un dueño.
"""
class ProductoImagenORM(Base, TimestampMixin):
    __tablename__ = "producto_imagen"
    __table_args__ = (
        CheckConstraint(
            "(producto_id IS NULL) <> (producto_unidad_id IS NULL)",
            name="ck_producto_imagen_un_solo_dueno",
        ),
        Index("ix_producto_imagen_producto", "producto_id"),
        Index("ix_producto_imagen_producto_unidad", "producto_unidad_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=True)
    producto_unidad_id = Column(
        PGUUID(as_uuid=True), ForeignKey("producto_unidad.id"), nullable=True
    )
    url = Column(String(500), nullable=False)
    alt_texto = Column(String(255), nullable=True)
    orden = Column(SmallInteger, nullable=False, default=0)
    es_principal = Column(Boolean, nullable=False, default=False)
