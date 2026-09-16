"""`PedidoProveedor`: máquina de estados y recepción parcial."""
import uuid
from decimal import Decimal

import pytest

from app.modules.proveedores.domain.entities import PedidoProveedor, PedidoProveedorLinea
from app.modules.proveedores.domain.value_objects import EstadoPedidoProveedor
from app.modules.proveedores.domain.exceptions import (
    PedidoProveedorSinLineas, PedidoNoEditable, TransicionPedidoProveedorInvalida,
)

PROVEEDOR = uuid.uuid4()
SUCURSAL = uuid.uuid4()
PRODUCTO = uuid.uuid4()
USER = uuid.uuid4()


def _linea(cantidad=Decimal("10"), precio=Decimal("5")):
    return PedidoProveedorLinea.crear(PRODUCTO, cantidad, precio)


def _pedido(**kw):
    return PedidoProveedor.crear(PROVEEDOR, SUCURSAL, [_linea()], **kw)


def test_sin_lineas_falla():
    with pytest.raises(PedidoProveedorSinLineas):
        PedidoProveedor.crear(PROVEEDOR, SUCURSAL, [])


def test_subtotal_es_suma_de_lineas():
    pedido = PedidoProveedor.crear(
        PROVEEDOR, SUCURSAL, [_linea(Decimal("10"), Decimal("5")), _linea(Decimal("2"), Decimal("3"))],
    )
    assert pedido.subtotal == Decimal("56")  # 10*5 + 2*3


def test_agregar_lineas_solo_en_borrador():
    pedido = _pedido()
    pedido.confirmar_envio(USER)
    with pytest.raises(PedidoNoEditable):
        pedido.agregar_lineas([_linea()])


def test_agregar_lineas_suma_a_producto_existente():
    pedido = _pedido()
    pedido.agregar_lineas([_linea(Decimal("5"), Decimal("5"))])
    assert len(pedido.lineas) == 1
    assert pedido.lineas[0].cantidad_solicitada == Decimal("15")


def test_confirmar_envio_dos_veces_falla():
    pedido = _pedido()
    pedido.confirmar_envio(USER)
    with pytest.raises(TransicionPedidoProveedorInvalida):
        pedido.confirmar_envio(USER)


def test_cancelar_desde_recibido_falla():
    pedido = _pedido()
    pedido.confirmar_envio(USER)
    pedido.registrar_recepcion_parcial({PRODUCTO: Decimal("10")})
    assert pedido.estado == EstadoPedidoProveedor.RECIBIDO
    with pytest.raises(TransicionPedidoProveedorInvalida):
        pedido.cancelar()


def test_recepcion_parcial_deja_estado_parcial():
    pedido = _pedido()
    pedido.confirmar_envio(USER)
    pedido.registrar_recepcion_parcial({PRODUCTO: Decimal("4")})
    assert pedido.estado == EstadoPedidoProveedor.PARCIAL
    pedido.registrar_recepcion_parcial({PRODUCTO: Decimal("6")})
    assert pedido.estado == EstadoPedidoProveedor.RECIBIDO
