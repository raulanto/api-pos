"""Devoluciones parciales / totales de una venta (fakes en memoria)."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import (
    Venta, DetalleVenta, CajaTurno, ESTADO_TURNO_ABIERTO,
)
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoDevolucion
from app.modules.ventas.domain.exceptions import (
    VentaNoDevolvible, CantidadDevolucionExcedida, DevolucionInvalida,
)
from app.modules.ventas.application.use_cases.devolver_venta import (
    DevolverVentaUseCase, DevolverVentaInput, DevolverVentaLineaInput,
)

SUC = uuid.uuid4()
USER = uuid.uuid4()
TURNO = uuid.uuid4()


def _venta(estado=EstadoVenta.PAGADA, cliente_id=None, precio="20", cantidad="5"):
    linea = DetalleVenta(
        id=uuid.uuid4(), venta_id=uuid.uuid4(), producto_id=uuid.uuid4(),
        cantidad=Decimal(cantidad), precio_unitario=Decimal(precio),
    )
    v = Venta(
        id=uuid.uuid4(), sucursal_id=SUC, caja_turno_id=TURNO, usuario_id=USER,
        cliente_id=cliente_id, estado=estado, lineas=[linea], pagos=[],
        created_at=datetime.now(timezone.utc),
    )
    linea.venta_id = v.id
    return v


class _VentaRepo:
    def __init__(self, venta):
        self._v = venta
        self.registrada = None

    async def obtener_por_id(self, vid, includes=frozenset()):
        return self._v if self._v.id == vid else None

    async def registrar_devolucion(self, venta):
        self.registrada = venta


class _DevRepo:
    def __init__(self):
        self.creadas = []
        self._por_key = {}

    async def obtener_por_idempotency_key(self, key):
        return self._por_key.get(key)

    async def crear(self, dev):
        self.creadas.append(dev)
        if dev.idempotency_key:
            self._por_key[dev.idempotency_key] = dev

    async def listar_por_venta(self, vid):
        return [d for d in self.creadas if d.venta_id == vid]


class _CajaRepo:
    async def obtener_por_id(self, tid):
        return CajaTurno(id=tid, sucursal_id=SUC, usuario_id=USER,
                         saldo_inicial=Decimal("0"), estado=ESTADO_TURNO_ABIERTO,
                         abierto_en=datetime.now(timezone.utc))


class _Inv:
    def __init__(self):
        self.repuesto = []

    async def convertir_a_base(self, producto_id, cantidad, producto_unidad_id=None):
        return cantidad

    async def reponer_parcial(self, venta_id, producto_id, cantidad_base, sucursal_id,
                              devolucion_id, usuario_id):
        self.repuesto.append((producto_id, cantidad_base))


class _ClienteRepo:
    def __init__(self):
        self.decrementos = []

    async def decrementar_saldo(self, cliente_id, monto):
        self.decrementos.append((cliente_id, monto))


class _Event:
    async def publicar(self, *a, **kw):
        pass


def _uc(venta, dev_repo=None, inv=None, cli=None):
    return DevolverVentaUseCase(
        _VentaRepo(venta), dev_repo or _DevRepo(), _CajaRepo(),
        inv or _Inv(), cli or _ClienteRepo(), _Event(),
    )


def _in(venta, cantidad, metodo=MetodoDevolucion.EFECTIVO, key=None):
    return DevolverVentaInput(
        venta_id=venta.id, caja_turno_id=TURNO, usuario_id=USER,
        metodo_devolucion=metodo,
        lineas=[DevolverVentaLineaInput(
            detalle_venta_id=venta.lineas[0].id, cantidad=Decimal(cantidad),
        )],
        idempotency_key=key,
    )


async def test_devolucion_parcial():
    v = _venta(precio="20", cantidad="5")
    inv = _Inv()
    dev = await _uc(v, inv=inv).ejecutar(_in(v, "2"))
    assert dev.monto_devuelto == Decimal("40.00")
    assert v.lineas[0].cantidad_devuelta == Decimal("2")
    assert v.estado == EstadoVenta.DEVUELTA_PARCIAL
    assert inv.repuesto == [(v.lineas[0].producto_id, Decimal("2"))]


async def test_devolucion_total():
    v = _venta(cantidad="5")
    await _uc(v).ejecutar(_in(v, "5"))
    assert v.estado == EstadoVenta.DEVUELTA_TOTAL


async def test_excede_lo_devolvible():
    v = _venta(cantidad="5")
    with pytest.raises(CantidadDevolucionExcedida):
        await _uc(v).ejecutar(_in(v, "6"))


async def test_venta_cancelada_no_devolvible():
    v = _venta(estado=EstadoVenta.CANCELADA)
    with pytest.raises(VentaNoDevolvible):
        await _uc(v).ejecutar(_in(v, "1"))


async def test_linea_ajena_a_la_venta():
    v = _venta()
    data = _in(v, "1")
    data.lineas[0].detalle_venta_id = uuid.uuid4()
    with pytest.raises(DevolucionInvalida):
        await _uc(v).ejecutar(data)


async def test_metodo_credito_baja_deuda_del_cliente():
    cid = uuid.uuid4()
    v = _venta(estado=EstadoVenta.PENDIENTE_PAGO, cliente_id=cid, precio="20", cantidad="5")
    cli = _ClienteRepo()
    await _uc(v, cli=cli).ejecutar(_in(v, "2", metodo=MetodoDevolucion.CREDITO))
    assert cli.decrementos == [(cid, Decimal("40.00"))]


async def test_idempotencia_no_repone_dos_veces():
    v = _venta(cantidad="5")
    dev_repo, inv = _DevRepo(), _Inv()
    uc = _uc(v, dev_repo=dev_repo, inv=inv)
    d1 = await uc.ejecutar(_in(v, "2", key="abc"))
    d2 = await uc.ejecutar(_in(v, "2", key="abc"))
    assert d1.id == d2.id
    assert len(inv.repuesto) == 1
