"""Máquina de estados del pedido + mapeo Pedido -> CrearVentaInput al facturar."""
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.pedidos.domain.entities import Pedido, DetallePedido, PedidoPago
from app.modules.pedidos.domain.value_objects import (
    TipoPedido, CanalPedido, EstadoPedido, EstadoEntrega,
)
from app.modules.pedidos.domain.exceptions import (
    DireccionEnvioRequerida, TransicionPedidoInvalida, PedidoYaFacturado,
    ProductoEnvioNoConfigurado,
)
from app.modules.pedidos.application.use_cases.facturar_pedido import (
    FacturarPedidoUseCase, FacturarPedidoInput,
)
from app.modules.pedidos.application.use_cases.actualizar_pedido import (
    ActualizarPedidoUseCase, ActualizarPedidoInput,
)


def _linea(precio="10", cant="2"):
    return DetallePedido.crear(
        producto_id=uuid.uuid4(), cantidad=Decimal(cant),
        precio_unitario=Decimal(precio), cantidad_en_unidad_base=Decimal(cant),
    )


def _pedido(tipo=TipoPedido.MOSTRADOR, costo_envio="0", **kw):
    return Pedido.crear(
        sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(), tipo=tipo,
        canal=CanalPedido.POS, lineas=[_linea(), _linea("5", "1")],
        costo_envio=Decimal(costo_envio),
        direccion_texto="Calle 123" if tipo == TipoPedido.DOMICILIO else None,
        **kw,
    )


# --------------------------------------------------------------------------- #
def test_domicilio_sin_direccion_falla():
    with pytest.raises(DireccionEnvioRequerida):
        Pedido.crear(
            sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
            tipo=TipoPedido.DOMICILIO, canal=CanalPedido.POS, lineas=[_linea()],
        )


def test_domicilio_arranca_entrega_pendiente():
    p = _pedido(TipoPedido.DOMICILIO)
    assert p.estado_entrega == EstadoEntrega.PENDIENTE
    assert _pedido(TipoPedido.MOSTRADOR).estado_entrega is None


def test_estado_pedido_transiciones():
    p = _pedido()
    p.confirmar()
    assert p.estado == EstadoPedido.CONFIRMADO
    with pytest.raises(TransicionPedidoInvalida):
        p.confirmar()                       # ya no está en borrador
    p.reabrir()
    assert p.estado == EstadoPedido.BORRADOR
    with pytest.raises(TransicionPedidoInvalida):
        p.marcar_facturado(uuid.uuid4())   # sólo desde confirmado
    p.confirmar()
    p.marcar_facturado(uuid.uuid4())
    assert p.estado == EstadoPedido.FACTURADO
    with pytest.raises(PedidoYaFacturado):
        p.cancelar()


def test_entrega_transiciones_y_timestamps():
    p = _pedido(TipoPedido.DOMICILIO)
    with pytest.raises(TransicionPedidoInvalida):
        p.avanzar_entrega(EstadoEntrega.EN_REPARTO)     # falta pasar por preparación
    p.avanzar_entrega(EstadoEntrega.EN_PREPARACION)
    p.avanzar_entrega(EstadoEntrega.EN_REPARTO)
    assert p.despachado_en is not None
    with pytest.raises(TransicionPedidoInvalida):
        p.avanzar_entrega(EstadoEntrega.FALLIDO)        # sin motivo
    p.avanzar_entrega(EstadoEntrega.ENTREGADO)
    assert p.estado_entrega == EstadoEntrega.ENTREGADO
    assert p.entregado_en is not None


def test_total_incluye_envio_y_descuenta_anticipos():
    p = _pedido(costo_envio="30")
    # 2*10 + 1*5 = 25 ; + envío 30 = 55
    assert p.total == Decimal("55")
    p.pagos.append(PedidoPago.crear(Decimal("20"), MetodoPago.TARJETA_DEBITO))
    assert p.total_anticipos == Decimal("20")
    assert p.saldo_por_cobrar == Decimal("35")


# --------------------------------------------------------------------------- #
class _PedidoRepo:
    def __init__(self, pedido):
        self._p = pedido
        self.actualizado = False

    async def obtener_por_id(self, pid, includes=frozenset()):
        return self._p if self._p.id == pid else None

    async def actualizar(self, pedido):
        self.actualizado = True


class _VentaRepo:
    async def obtener_por_id(self, vid, includes=frozenset()):
        return None


class _CrearVentaUC:
    def __init__(self):
        self.entrada = None

    async def ejecutar(self, entrada):
        self.entrada = entrada
        return SimpleNamespace(
            id=uuid.uuid4(), sucursal_id=entrada.sucursal_id, total=Decimal("0"),
        )


class _EventPort:
    async def publicar(self, *a, **k):
        return None


async def _facturar(pedido, producto_envio_id, **kw):
    repo = _PedidoRepo(pedido)
    venta_uc = _CrearVentaUC()
    uc = FacturarPedidoUseCase(repo, _VentaRepo(), venta_uc, _EventPort(), producto_envio_id)
    venta = await uc.ejecutar(FacturarPedidoInput(
        pedido_id=pedido.id, usuario_id=uuid.uuid4(), caja_turno_id=uuid.uuid4(), **kw,
    ))
    return venta, venta_uc.entrada, repo


async def test_facturar_congela_lineas_y_agrega_envio():
    p = _pedido(costo_envio="30")
    p.confirmar()
    envio_id = uuid.uuid4()
    venta, entrada, repo = await _facturar(p, envio_id)

    assert entrada.lineas == [] and entrada.lineas_congeladas is not None
    assert len(entrada.lineas_congeladas) == 3          # 2 líneas + envío
    envio = entrada.lineas_congeladas[-1]
    assert envio.producto_id == envio_id
    assert envio.precio_unitario == Decimal("30")
    assert p.estado == EstadoPedido.FACTURADO
    assert p.venta_id == venta.id
    assert repo.actualizado


async def test_facturar_recalcular_usa_lineas_input():
    p = _pedido(costo_envio="0")
    p.confirmar()
    _, entrada, _ = await _facturar(p, uuid.uuid4(), recalcular_precios=True)
    assert entrada.lineas_congeladas is None
    assert len(entrada.lineas) == 2


async def test_facturar_envio_sin_producto_configurado_falla():
    p = _pedido(costo_envio="15")
    p.confirmar()
    with pytest.raises(ProductoEnvioNoConfigurado):
        await _facturar(p, None)


async def test_facturar_exige_confirmado():
    p = _pedido()                       # sigue en borrador
    with pytest.raises(TransicionPedidoInvalida):
        await _facturar(p, uuid.uuid4())


# --------------------------------------------------------------------------- #
# Editar el `tipo`
def test_cambiar_tipo_domicilio_a_mostrador_limpia_envio():
    p = _pedido(TipoPedido.DOMICILIO, costo_envio="30")
    assert p.estado_entrega == EstadoEntrega.PENDIENTE
    p.cambiar_tipo(TipoPedido.MOSTRADOR)
    assert p.tipo == TipoPedido.MOSTRADOR
    assert p.estado_entrega is None
    assert p.direccion_texto is None
    assert p.costo_envio == Decimal("0")


def test_cambiar_tipo_mostrador_a_domicilio_arranca_entrega():
    p = _pedido(TipoPedido.MOSTRADOR)
    assert p.estado_entrega is None
    p.cambiar_tipo(TipoPedido.DOMICILIO)
    assert p.estado_entrega == EstadoEntrega.PENDIENTE


async def test_actualizar_pedido_cambia_tipo_a_mostrador():
    """Reproduce el bug: front cambia a mostrador y manda direccion_texto=None."""
    p = _pedido(TipoPedido.DOMICILIO, costo_envio="30")
    repo = _PedidoRepo(p)
    out = await ActualizarPedidoUseCase(repo, None).ejecutar(ActualizarPedidoInput(
        pedido_id=p.id, tipo=TipoPedido.MOSTRADOR, direccion_texto=None,
    ))
    assert out.tipo == TipoPedido.MOSTRADOR
    assert out.estado_entrega is None
    assert repo.actualizado


async def test_actualizar_pedido_a_domicilio_sin_direccion_falla():
    p = _pedido(TipoPedido.MOSTRADOR)
    with pytest.raises(DireccionEnvioRequerida):
        await ActualizarPedidoUseCase(_PedidoRepo(p), None).ejecutar(ActualizarPedidoInput(
            pedido_id=p.id, tipo=TipoPedido.DOMICILIO,
        ))
