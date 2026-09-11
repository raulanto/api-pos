"""Máquina de estados del pedido, servicios con responsable, y facturación."""
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
    ServicioSinResponsable, ResponsableInvalido,
)
from app.modules.pedidos.application.use_cases.facturar_pedido import (
    FacturarPedidoUseCase, FacturarPedidoInput,
)
from app.modules.pedidos.application.use_cases.actualizar_pedido import (
    ActualizarPedidoUseCase, ActualizarPedidoInput,
)
from app.modules.pedidos.application.use_cases.gestionar_pedido import (
    AsignarServiciosUseCase, AsignarServiciosInput,
)
from app.modules.pedidos.application.use_cases.crear_pedido import cotizar_a_detalles


def _linea(precio="10", cant="2", *, es_servicio=False, asignado_a=None):
    return DetallePedido.crear(
        producto_id=uuid.uuid4(), cantidad=Decimal(cant),
        precio_unitario=Decimal(precio), cantidad_en_unidad_base=Decimal(cant),
        es_servicio=es_servicio, asignado_a=asignado_a,
    )


def _pedido(tipo=TipoPedido.MOSTRADOR, lineas=None, **kw):
    return Pedido.crear(
        sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(), tipo=tipo,
        canal=CanalPedido.POS, lineas=lineas or [_linea(), _linea("5", "1")],
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
    assert _pedido(TipoPedido.DOMICILIO).estado_entrega == EstadoEntrega.PENDIENTE
    assert _pedido(TipoPedido.MOSTRADOR).estado_entrega is None


def test_estado_pedido_transiciones():
    p = _pedido()
    p.confirmar()
    assert p.estado == EstadoPedido.CONFIRMADO
    with pytest.raises(TransicionPedidoInvalida):
        p.confirmar()
    p.reabrir()
    with pytest.raises(TransicionPedidoInvalida):
        p.marcar_facturado(uuid.uuid4())
    p.confirmar()
    p.marcar_facturado(uuid.uuid4())
    assert p.estado == EstadoPedido.FACTURADO
    with pytest.raises(PedidoYaFacturado):
        p.cancelar()


def test_entrega_transiciones_y_timestamps():
    p = _pedido(TipoPedido.DOMICILIO)
    with pytest.raises(TransicionPedidoInvalida):
        p.avanzar_entrega(EstadoEntrega.EN_REPARTO)
    p.avanzar_entrega(EstadoEntrega.EN_PREPARACION)
    p.avanzar_entrega(EstadoEntrega.EN_REPARTO)
    assert p.despachado_en is not None
    with pytest.raises(TransicionPedidoInvalida):
        p.avanzar_entrega(EstadoEntrega.FALLIDO)          # sin motivo
    p.avanzar_entrega(EstadoEntrega.ENTREGADO)
    assert p.entregado_en is not None


def test_total_y_anticipos():
    p = _pedido()
    assert p.total == Decimal("25")                       # 2*10 + 1*5
    p.pagos.append(PedidoPago.crear(Decimal("20"), MetodoPago.TARJETA_DEBITO))
    assert p.total_anticipos == Decimal("20")
    assert p.saldo_por_cobrar == Decimal("5")


# --------------------------------------------------------------------------- #
# Servicios con responsable
def test_confirmar_bloquea_servicio_sin_responsable():
    p = _pedido(lineas=[_linea(), _linea("50", "1", es_servicio=True)])
    assert len(p.servicios_sin_responsable) == 1
    with pytest.raises(ServicioSinResponsable):
        p.confirmar()


def test_confirmar_ok_con_responsable():
    who = uuid.uuid4()
    p = _pedido(lineas=[_linea(), _linea("50", "1", es_servicio=True, asignado_a=who)])
    p.confirmar()
    assert p.estado == EstadoPedido.CONFIRMADO


def test_asignar_servicio_en_linea():
    serv = _linea("50", "1", es_servicio=True)
    p = _pedido(lineas=[_linea(), serv])
    who = uuid.uuid4()
    p.asignar_servicio(serv.id, who)
    assert serv.asignado_a == who
    # una línea que no es servicio no acepta asignación
    with pytest.raises(ResponsableInvalido):
        p.asignar_servicio(p.lineas[0].id, who)


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
    """Fake: `ejecutar` captura la entrada; `cotizar` devuelve líneas 1:1."""
    def __init__(self):
        self.entrada = None

    async def ejecutar(self, entrada):
        self.entrada = entrada
        return SimpleNamespace(
            id=uuid.uuid4(), sucursal_id=entrada.sucursal_id, total=Decimal("0"),
        )

    async def cotizar(self, data):
        lineas = [
            SimpleNamespace(
                producto_id=l.producto_id, producto_unidad_id=l.producto_unidad_id,
                cantidad=l.cantidad, precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea, impuesto_tasa=l.impuesto_tasa,
                promo_id=None, promo_etiqueta=None, promo_descuento=Decimal("0"),
                cantidad_en_unidad_base=l.cantidad, subtotal=l.cantidad * l.precio_unitario,
                stock_disponible=None, hay_stock=True,
                es_servicio=(i == 1),          # la 2da línea es "servicio"
            )
            for i, l in enumerate(data.lineas)
        ]
        return SimpleNamespace(lineas=lineas)


class _EventPort:
    async def publicar(self, *a, **k):
        return None


class _UsuarioRepo:
    def __init__(self, activos=True):
        self._activos = activos

    async def obtener_por_id(self, uid, includes=frozenset()):
        return SimpleNamespace(id=uid, activo=self._activos)


async def _facturar(pedido, **kw):
    repo = _PedidoRepo(pedido)
    venta_uc = _CrearVentaUC()
    uc = FacturarPedidoUseCase(repo, _VentaRepo(), venta_uc, _EventPort())
    venta = await uc.ejecutar(FacturarPedidoInput(
        pedido_id=pedido.id, usuario_id=uuid.uuid4(), caja_turno_id=uuid.uuid4(), **kw,
    ))
    return venta, venta_uc.entrada, repo


async def test_facturar_congela_lineas():
    who = uuid.uuid4()
    p = _pedido(lineas=[_linea(), _linea("50", "1", es_servicio=True, asignado_a=who)])
    p.confirmar()
    venta, entrada, repo = await _facturar(p)
    assert entrada.lineas == [] and entrada.lineas_congeladas is not None
    assert len(entrada.lineas_congeladas) == 2      # las 2 del pedido, sin extras
    assert p.estado == EstadoPedido.FACTURADO
    assert p.venta_id == venta.id
    assert repo.actualizado


async def test_facturar_recalcular_usa_lineas_input():
    p = _pedido()
    p.confirmar()
    _, entrada, _ = await _facturar(p, recalcular_precios=True)
    assert entrada.lineas_congeladas is None
    assert len(entrada.lineas) == 2


async def test_facturar_exige_confirmado():
    p = _pedido()                                   # sigue en borrador
    with pytest.raises(TransicionPedidoInvalida):
        await _facturar(p)


async def test_asignar_servicios_use_case():
    serv = _linea("50", "1", es_servicio=True)
    p = _pedido(lineas=[_linea(), serv])
    repo = _PedidoRepo(p)
    who = uuid.uuid4()
    out = await AsignarServiciosUseCase(repo, _EventPort(), _UsuarioRepo()).ejecutar(
        AsignarServiciosInput(pedido_id=p.id, usuario_id=uuid.uuid4(),
                              asignaciones=[(serv.id, who)])
    )
    assert next(l for l in out.lineas if l.id == serv.id).asignado_a == who
    assert repo.actualizado


async def test_asignar_servicios_responsable_inactivo_falla():
    serv = _linea("50", "1", es_servicio=True)
    p = _pedido(lineas=[_linea(), serv])
    with pytest.raises(ResponsableInvalido):
        await AsignarServiciosUseCase(
            _PedidoRepo(p), _EventPort(), _UsuarioRepo(activos=False),
        ).ejecutar(AsignarServiciosInput(
            pedido_id=p.id, usuario_id=uuid.uuid4(), asignaciones=[(serv.id, uuid.uuid4())],
        ))


async def test_cotizar_a_detalles_marca_servicio_y_conserva_responsable():
    who = uuid.uuid4()
    fuente = SimpleNamespace(
        sucursal_id=uuid.uuid4(), descuento_total=Decimal("0"),
        cliente_segmento=None, codigo_cupon=None, telefono=None,
        lineas=[
            SimpleNamespace(producto_id=uuid.uuid4(), cantidad=Decimal("1"),
                            precio_unitario=Decimal("10"), descuento_linea=Decimal("0"),
                            impuesto_tasa=Decimal("0"), producto_unidad_id=None,
                            asignado_a=None),
            SimpleNamespace(producto_id=uuid.uuid4(), cantidad=Decimal("1"),
                            precio_unitario=Decimal("50"), descuento_linea=Decimal("0"),
                            impuesto_tasa=Decimal("0"), producto_unidad_id=None,
                            asignado_a=who),
        ],
    )
    dets = await cotizar_a_detalles(_CrearVentaUC(), fuente)
    assert dets[0].es_servicio is False and dets[0].asignado_a is None
    assert dets[1].es_servicio is True and dets[1].asignado_a == who


# --------------------------------------------------------------------------- #
# Editar el `tipo`
def test_cambiar_tipo_domicilio_a_mostrador_limpia_entrega():
    p = _pedido(TipoPedido.DOMICILIO)
    assert p.estado_entrega == EstadoEntrega.PENDIENTE
    p.cambiar_tipo(TipoPedido.MOSTRADOR)
    assert p.tipo == TipoPedido.MOSTRADOR
    assert p.estado_entrega is None
    assert p.direccion_texto is None


def test_cambiar_tipo_mostrador_a_domicilio_arranca_entrega():
    p = _pedido(TipoPedido.MOSTRADOR)
    p.cambiar_tipo(TipoPedido.DOMICILIO)
    assert p.estado_entrega == EstadoEntrega.PENDIENTE


async def test_actualizar_pedido_cambia_tipo_a_mostrador():
    """Reproduce el bug viejo: front cambia a mostrador y manda direccion_texto=None."""
    p = _pedido(TipoPedido.DOMICILIO)
    repo = _PedidoRepo(p)
    out = await ActualizarPedidoUseCase(repo, None, None).ejecutar(ActualizarPedidoInput(
        pedido_id=p.id, tipo=TipoPedido.MOSTRADOR, direccion_texto=None,
    ))
    assert out.tipo == TipoPedido.MOSTRADOR
    assert out.estado_entrega is None
    assert repo.actualizado


async def test_actualizar_pedido_a_domicilio_sin_direccion_falla():
    p = _pedido(TipoPedido.MOSTRADOR)
    with pytest.raises(DireccionEnvioRequerida):
        await ActualizarPedidoUseCase(_PedidoRepo(p), None, None).ejecutar(
            ActualizarPedidoInput(pedido_id=p.id, tipo=TipoPedido.DOMICILIO)
        )
