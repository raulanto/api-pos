"""`RegistrarRecepcionUseCase`: aplica ENTRADA/MERMA en inventario y actualiza
el pedido si corresponde."""
import uuid
from decimal import Decimal

import pytest

from app.modules.proveedores.domain.value_objects import MotivoDefecto, AccionDefecto
from app.modules.proveedores.domain.exceptions import DefectoInvalido
from app.modules.proveedores.application.use_cases.registrar_recepcion import (
    RegistrarRecepcionUseCase, RegistrarRecepcionInput, LineaRecepcionInput,
)
from app.modules.proveedores.domain.entities import PedidoProveedor, PedidoProveedorLinea
from app.modules.inventario.domain.value_objects import TipoMovimiento

PROVEEDOR = uuid.uuid4()
SUCURSAL = uuid.uuid4()
PRODUCTO = uuid.uuid4()
USER = uuid.uuid4()


class _RecepcionRepo:
    def __init__(self):
        self.guardadas = []

    async def guardar(self, recepcion):
        self.guardadas.append(recepcion)


class _PedidoRepo:
    def __init__(self, pedido=None):
        self._pedido = pedido
        self.actualizados = []

    async def obtener_por_id(self, pedido_id, para_actualizar=False):
        return self._pedido

    async def actualizar(self, pedido):
        self.actualizados.append(pedido)


class _AplicarMovimientoFake:
    def __init__(self):
        self.llamadas = []

    async def ejecutar(self, data):
        self.llamadas.append(data)


def _linea_buena(cantidad=Decimal("10")):
    return LineaRecepcionInput(producto_id=PRODUCTO, cantidad_recibida_buena=cantidad)


async def test_defecto_sin_motivo_falla():
    uc = RegistrarRecepcionUseCase(_RecepcionRepo(), _PedidoRepo(), _AplicarMovimientoFake())
    with pytest.raises(DefectoInvalido):
        await uc.ejecutar(RegistrarRecepcionInput(
            proveedor_id=PROVEEDOR, sucursal_id=SUCURSAL, recibido_por=USER,
            lineas=[LineaRecepcionInput(
                producto_id=PRODUCTO, cantidad_recibida_buena=Decimal("5"),
                cantidad_defectuosa=Decimal("2"),
            )],
        ))


async def test_motivo_sin_defecto_falla():
    uc = RegistrarRecepcionUseCase(_RecepcionRepo(), _PedidoRepo(), _AplicarMovimientoFake())
    with pytest.raises(DefectoInvalido):
        await uc.ejecutar(RegistrarRecepcionInput(
            proveedor_id=PROVEEDOR, sucursal_id=SUCURSAL, recibido_por=USER,
            lineas=[LineaRecepcionInput(
                producto_id=PRODUCTO, cantidad_recibida_buena=Decimal("5"),
                motivo_defecto=MotivoDefecto.DANADO, accion_defecto=AccionDefecto.MERMA,
            )],
        ))


async def test_linea_buena_genera_entrada():
    aplicar = _AplicarMovimientoFake()
    uc = RegistrarRecepcionUseCase(_RecepcionRepo(), _PedidoRepo(), aplicar)
    await uc.ejecutar(RegistrarRecepcionInput(
        proveedor_id=PROVEEDOR, sucursal_id=SUCURSAL, recibido_por=USER,
        lineas=[_linea_buena(Decimal("10"))],
    ))
    assert len(aplicar.llamadas) == 1
    assert aplicar.llamadas[0].tipo == TipoMovimiento.ENTRADA
    assert aplicar.llamadas[0].cantidad == Decimal("10")


async def test_defecto_merma_genera_movimiento_merma():
    aplicar = _AplicarMovimientoFake()
    uc = RegistrarRecepcionUseCase(_RecepcionRepo(), _PedidoRepo(), aplicar)
    await uc.ejecutar(RegistrarRecepcionInput(
        proveedor_id=PROVEEDOR, sucursal_id=SUCURSAL, recibido_por=USER,
        lineas=[LineaRecepcionInput(
            producto_id=PRODUCTO, cantidad_recibida_buena=Decimal("8"),
            cantidad_defectuosa=Decimal("2"), motivo_defecto=MotivoDefecto.DANADO,
            accion_defecto=AccionDefecto.MERMA,
        )],
    ))
    tipos = [c.tipo for c in aplicar.llamadas]
    assert TipoMovimiento.ENTRADA in tipos and TipoMovimiento.MERMA in tipos


async def test_defecto_devolucion_no_genera_movimiento():
    aplicar = _AplicarMovimientoFake()
    uc = RegistrarRecepcionUseCase(_RecepcionRepo(), _PedidoRepo(), aplicar)
    await uc.ejecutar(RegistrarRecepcionInput(
        proveedor_id=PROVEEDOR, sucursal_id=SUCURSAL, recibido_por=USER,
        lineas=[LineaRecepcionInput(
            producto_id=PRODUCTO, cantidad_recibida_buena=Decimal("0"),
            cantidad_defectuosa=Decimal("3"), motivo_defecto=MotivoDefecto.INCOMPLETO,
            accion_defecto=AccionDefecto.DEVOLUCION,
        )],
    ))
    assert aplicar.llamadas == []   # ni ENTRADA (0) ni MERMA (accion != merma)


async def test_actualiza_pedido_si_viene_pedido_id():
    pedido = PedidoProveedor.crear(
        PROVEEDOR, SUCURSAL, [PedidoProveedorLinea.crear(PRODUCTO, Decimal("10"), Decimal("5"))],
    )
    pedido.confirmar_envio(USER)
    pedido_repo = _PedidoRepo(pedido)
    uc = RegistrarRecepcionUseCase(_RecepcionRepo(), pedido_repo, _AplicarMovimientoFake())
    await uc.ejecutar(RegistrarRecepcionInput(
        proveedor_id=PROVEEDOR, sucursal_id=SUCURSAL, recibido_por=USER,
        lineas=[_linea_buena(Decimal("10"))], pedido_id=pedido.id,
    ))
    assert len(pedido_repo.actualizados) == 1
    assert pedido.lineas[0].cantidad_recibida == Decimal("10")
