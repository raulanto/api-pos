import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, SoftDeleteMixin


"""
    Tabla: categoria
    Descripcion: Tabla que almacena las categorias de los productos.
    Columnas:
    - id: ID de la categoria.
    - nombre: Nombre de la categoria.
    - categoria_padre_id: ID de la categoria padre.
    - created_at: Fecha de creacion.
    - updated_at: Fecha de actualizacion.
    - deleted_at: Fecha de eliminacion.
    
    Relaciones:
    - categoria_padre_id: FK a categoria.id
    - productos: 1:N con producto.categoria_id

"""
class CategoriaORM(Base, SoftDeleteMixin):
    __tablename__ = "categoria"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    categoria_padre_id = Column(PGUUID(as_uuid=True), ForeignKey("categoria.id"), nullable=True)

    # Solo lectura, para `?include=padre`.
    padre = relationship("CategoriaORM", remote_side=[id], viewonly=True, lazy="raise")
