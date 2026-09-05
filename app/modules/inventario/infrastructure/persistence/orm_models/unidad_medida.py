import uuid
from sqlalchemy import Column, String, SmallInteger, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

"""
    Tabla: unidad_medida
    Descripcion: Catálogo normalizado de unidades de medida. Reemplaza el texto
        libre de `producto.unidad_medida` / `producto_unidad.unidad_medida` (que
        se conservan como fallback mientras se completa el backfill).
    Columnas:
    - id
    - codigo: clave corta única ("kg", "l", "pza", "reja")
    - nombre: nombre visible ("Kilogramo")
    - tipo_magnitud: conteo | masa | volumen | longitud | tiempo
    - decimales: decimales admitidos en una cantidad de esta unidad (0..6)
    - activo, created_at, updated_at

    Restricciones:
    - uq_unidad_medida_codigo: `codigo` único (entre activas e inactivas)
    - ck_unidad_medida_decimales: 0 <= decimales <= 6
"""
class UnidadMedidaORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "unidad_medida"
    __table_args__ = (
        CheckConstraint(
            "decimales >= 0 AND decimales <= 6", name="ck_unidad_medida_decimales"
        ),
        Index("uq_unidad_medida_codigo", "codigo", unique=True),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(20), nullable=False)
    nombre = Column(String(60), nullable=False)
    tipo_magnitud = Column(String(20), nullable=False)
    decimales = Column(SmallInteger, nullable=False, default=0)
