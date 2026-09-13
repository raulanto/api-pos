"""`ProductoProveedor`: validaciones de la entidad + un solo principal activo
por producto."""
import uuid
from decimal import Decimal

import pytest

from app.modules.proveedores.domain.entities import ProductoProveedor
from app.modules.proveedores.domain.exceptions import (
    ProductoProveedorYaExiste, YaHayProveedorPrincipal,
)
from app.modules.proveedores.application.use_cases.gestionar_producto_proveedor import (
    VincularProductoProveedorUseCase, VincularProductoProveedorInput,
    MarcarProveedorPrincipalUseCase,
)

PRODUCTO = uuid.uuid4()
PROVEEDOR_A = uuid.uuid4()
PROVEEDOR_B = uuid.uuid4()


class _Repo:
    def __init__(self, vinculos=None):
        self._v = {v.id: v for v in (vinculos or [])}

    async def obtener_por_id(self, id_):
        return self._v.get(id_)

    async def obtener_por_par(self, producto_id, proveedor_id):
        return next(
            (v for v in self._v.values() if v.producto_id == producto_id and v.proveedor_id == proveedor_id),
            None,
        )

    async def guardar(self, pp):
        self._v[pp.id] = pp

    async def actualizar(self, pp):
        self._v[pp.id] = pp

    async def obtener_principal(self, producto_id):
        return next(
            (v for v in self._v.values() if v.producto_id == producto_id and v.es_proveedor_principal and v.activo),
            None,
        )


def _crear(**kw):
    base = dict(
        producto_id=PRODUCTO, proveedor_id=PROVEEDOR_A, precio_compra=Decimal("10"),
        tiempo_entrega_dias=5, stock_minimo=Decimal("20"), cantidad_reorden=Decimal("50"),
    )
    base.update(kw)
    return ProductoProveedor.crear(**base)


def test_precio_negativo_falla():
    with pytest.raises(ValueError):
        _crear(precio_compra=Decimal("-1"))


def test_stock_maximo_menor_a_minimo_falla():
    with pytest.raises(ValueError):
        _crear(stock_minimo=Decimal("50"), stock_maximo=Decimal("10"))


def test_cantidad_reorden_no_positiva_falla():
    with pytest.raises(ValueError):
        _crear(cantidad_reorden=Decimal("0"))


async def test_vincular_ya_existente_activo_falla():
    existente = _crear()
    repo = _Repo([existente])
    with pytest.raises(ProductoProveedorYaExiste):
        await VincularProductoProveedorUseCase(repo).ejecutar(VincularProductoProveedorInput(
            producto_id=PRODUCTO, proveedor_id=PROVEEDOR_A, precio_compra=Decimal("10"),
            tiempo_entrega_dias=5, stock_minimo=Decimal("20"), cantidad_reorden=Decimal("50"),
        ))


async def test_marcar_principal_ya_hay_otro_quita_el_viejo():
    a = _crear(proveedor_id=PROVEEDOR_A, es_proveedor_principal=True)
    b = _crear(proveedor_id=PROVEEDOR_B)
    repo = _Repo([a, b])
    resultado = await MarcarProveedorPrincipalUseCase(repo).ejecutar(b.id)
    assert resultado.es_proveedor_principal
    assert not a.es_proveedor_principal


def test_desactivar_quita_principal():
    pp = _crear(es_proveedor_principal=True)
    pp.desactivar()
    assert not pp.activo
    assert not pp.es_proveedor_principal
