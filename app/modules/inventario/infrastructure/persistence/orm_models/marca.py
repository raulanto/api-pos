import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base, SoftDeleteMixin


"""
    Tabla: marca
    Descripcion: Tabla que almacena las marcas de los productos.
    Columnas:
    - id: ID de la marca.
    - nombre: Nombre de la marca.
    - created_at: Fecha de creacion.
    - updated_at: Fecha de actualizacion.
    - deleted_at: Fecha de eliminacion.

    Relaciones:
    - productos: 1:N con producto.marca_id
"""
class MarcaORM(Base, SoftDeleteMixin):
    __tablename__ = "marca"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
