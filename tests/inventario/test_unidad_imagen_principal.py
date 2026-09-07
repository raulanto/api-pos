"""`to_domain_unidad`: la portada de la presentación entra sólo si el repo la
trajo cargada (`?include=unidades`); si no, la relación `lazy="raise"` no se toca.
"""
import uuid
from decimal import Decimal

import app.main  # noqa: F401  -- registra todo el ORM (mappers cruzados: usuarios, etc.)
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_unidad
from app.modules.inventario.infrastructure.persistence.orm_models import (
    ProductoUnidadORM, ProductoImagenORM,
)


def _unidad_orm() -> ProductoUnidadORM:
    return ProductoUnidadORM(
        id=uuid.uuid4(), producto_id=uuid.uuid4(), nombre="Reja x24",
        unidad_medida="pza", factor=Decimal("24"), precio_venta=Decimal("100"),
    )


def test_relacion_no_cargada_devuelve_none():
    assert to_domain_unidad(_unidad_orm()).imagen_principal is None


def test_relacion_cargada_mapea_la_portada():
    orm = _unidad_orm()
    img = ProductoImagenORM(
        id=uuid.uuid4(), producto_unidad_id=orm.id, url="http://cdn/x.png",
        object_key=None, alt_texto=None, orden=0, es_principal=True,
    )
    orm.__dict__["imagen_principal"] = img          # como lo dejaría selectinload

    u = to_domain_unidad(orm)
    assert u.imagen_principal is not None
    assert u.imagen_principal.url == "http://cdn/x.png"
