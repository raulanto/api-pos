"""`FacturarCitaUseCase`: cobra una cita completada reusando `CrearVentaUseCase`
(mismo patrón que `pedidos.FacturarPedidoUseCase`)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.agenda.domain.entities import Cita
from app.modules.agenda.domain.exceptions import CitaNoFacturable, CitaYaFacturada
from app.modules.agenda.application.use_cases.facturar_cita import (
    FacturarCitaUseCase, FacturarCitaInput,
)
from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.value_objects import TipoProducto
from app.modules.ventas.domain.entities import CajaTurno, ESTADO_TURNO_ABIERTO
from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.ventas.application.use_cases.crear_venta import CrearVentaUseCase, PagoInput

SUC = uuid.uuid4()
SERVICIO = uuid.uuid4()
USER = uuid.uuid4()
EMP = uuid.uuid4()
TURNO = uuid.uuid4()
INICIO = datetime.now(timezone.utc)
FIN = INICIO + timedelta(minutes=30)


def _servicio():
    return Producto.crear(
        sku="SRV", nombre="Corte", categoria_id=uuid.uuid4(), unidad_medida="servicio",
        precio_venta=Decimal("200"), costo=Decimal("0"), impuesto_tasa=Decimal("0"),
        tipo=TipoProducto.SERVICIO, duracion_minutos=30,
    )


def _cita_completada():
    cita = Cita.crear(SERVICIO, SUC, INICIO, FIN, USER)
    cita.ofertar([EMP])
    cita.aceptar(EMP)
    cita.completar()
    return cita


class _CitaRepo:
    def __init__(self, cita):
        self._c = cita

    async def obtener_por_id(self, cid, para_actualizar=False):
        return self._c if self._c.id == cid else None

    async def actualizar(self, cita):
        pass


class _ProductoRepo:
    def __init__(self, producto):
        self._p = producto

    async def obtener_por_id(self, pid, includes=frozenset()):
        return self._p


class _CajaRepo:
    async def obtener_por_id(self, tid):
        return CajaTurno(
            id=tid, sucursal_id=SUC, caja_id=uuid.uuid4(), usuario_id=USER,
            saldo_inicial=Decimal("0"), estado=ESTADO_TURNO_ABIERTO,
            abierto_en=datetime.now(timezone.utc),
        )


class _VentaRepo:
    def __init__(self):
        self.guardada = None

    async def obtener_por_idempotency_key(self, k):
        return None

    async def guardar(self, venta):
        self.guardada = venta


class _Inventario:
    async def descontar_stock(self, **kw):
        pass


class _Event:
    async def publicar(self, *a, **kw):
        pass


def _venta_uc():
    return CrearVentaUseCase(_VentaRepo(), _CajaRepo(), _Inventario(), object(), _Event())


async def test_factura_cita_completada_congela_precio_y_cruza_ids():
    cita = _cita_completada()
    uc = FacturarCitaUseCase(_CitaRepo(cita), _ProductoRepo(_servicio()), _venta_uc())
    venta = await uc.ejecutar(FacturarCitaInput(
        cita_id=cita.id, usuario_id=USER, caja_turno_id=TURNO,
        pagos=[PagoInput(monto=Decimal("200"), metodo_pago=MetodoPago.EFECTIVO)],
    ))
    detalle = venta.lineas[0]
    assert detalle.cita_id == cita.id
    assert detalle.precio_unitario == Decimal("200")
    assert cita.venta_detalle_id == detalle.id


async def test_factura_cita_no_completada_falla():
    cita = Cita.crear(SERVICIO, SUC, INICIO, FIN, USER)
    uc = FacturarCitaUseCase(_CitaRepo(cita), _ProductoRepo(_servicio()), _venta_uc())
    with pytest.raises(CitaNoFacturable):
        await uc.ejecutar(FacturarCitaInput(cita_id=cita.id, usuario_id=USER, caja_turno_id=TURNO))


async def test_factura_cita_ya_facturada_falla():
    cita = _cita_completada()
    cita.vincular_venta(uuid.uuid4())
    uc = FacturarCitaUseCase(_CitaRepo(cita), _ProductoRepo(_servicio()), _venta_uc())
    with pytest.raises(CitaYaFacturada):
        await uc.ejecutar(FacturarCitaInput(cita_id=cita.id, usuario_id=USER, caja_turno_id=TURNO))
