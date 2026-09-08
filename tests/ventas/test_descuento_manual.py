"""`CrearVentaUseCase`: descuento manual con permiso + motivo + tope de % por rol."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import CajaTurno, ESTADO_TURNO_ABIERTO
from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.ventas.domain.exceptions import (
    DescuentoManualNoAutorizado, DescuentoManualExcedeTope, MotivoDescuentoRequerido,
)
from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CrearVentaInput, LineaInput, PagoInput,
)

SUC = uuid.uuid4()
PROD = uuid.uuid4()
TURNO = uuid.uuid4()
ROL = uuid.uuid4()


class _CajaRepo:
    async def obtener_por_id(self, tid):
        return CajaTurno(id=tid, sucursal_id=SUC, usuario_id=uuid.uuid4(),
                         saldo_inicial=Decimal("0"), estado=ESTADO_TURNO_ABIERTO,
                         abierto_en=datetime.now(timezone.utc))


class _VentaRepo:
    def __init__(self): self.guardada = None
    async def obtener_por_idempotency_key(self, k): return None
    async def guardar(self, venta): self.guardada = venta


class _Inventario:
    async def precio_mayoreo_aplicable(self, pid, cant): return None
    async def convertir_a_base(self, producto_id, cantidad, producto_unidad_id=None):
        return cantidad
    async def stock_disponible(self, *a, **kw): return None
    async def descontar_stock(self, **kw): pass


class _Event:
    def __init__(self): self.eventos = []
    async def publicar(self, nombre, payload): self.eventos.append((nombre, payload))


class _DescuentoConfig:
    def __init__(self, pct_max): self._p = pct_max
    async def pct_max_para_rol(self, rol_id): return self._p


def _uc(event=None, pct_max=None):
    return CrearVentaUseCase(
        _VentaRepo(), _CajaRepo(), _Inventario(), None, event or _Event(),
        descuento_config=_DescuentoConfig(pct_max),
    )


def _input(*, descuento_linea="0", descuento_total="0", motivo=None,
           puede=True, precio="100", cantidad="1"):
    total_bruto = Decimal(precio) * Decimal(cantidad)
    pago = total_bruto - Decimal(descuento_linea) - Decimal(descuento_total)
    return CrearVentaInput(
        sucursal_id=SUC, caja_turno_id=TURNO, usuario_id=uuid.uuid4(),
        cliente_id=None, descuento_total=Decimal(descuento_total),
        lineas=[LineaInput(producto_id=PROD, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal(precio),
                           descuento_linea=Decimal(descuento_linea))],
        pagos=[PagoInput(monto=pago, metodo_pago=MetodoPago.EFECTIVO)],
        motivo_descuento=motivo, puede_descuento_manual=puede, rol_id=ROL,
    )


async def test_sin_permiso_rechaza():
    with pytest.raises(DescuentoManualNoAutorizado):
        await _uc().ejecutar(_input(descuento_linea="10", motivo="x", puede=False))


async def test_sin_motivo_rechaza():
    with pytest.raises(MotivoDescuentoRequerido):
        await _uc().ejecutar(_input(descuento_total="10", motivo=None))


async def test_excede_tope_de_rol():
    with pytest.raises(DescuentoManualExcedeTope):
        await _uc(pct_max=Decimal("10")).ejecutar(
            _input(descuento_linea="20", motivo="promo amigo", precio="100")
        )


async def test_bajo_el_tope_ok_y_se_audita():
    ev = _Event()
    venta = await _uc(ev, pct_max=Decimal("15")).ejecutar(
        _input(descuento_linea="10", motivo="cliente frecuente", precio="100")
    )
    assert venta.motivo_descuento == "cliente frecuente"
    assert any(n == "DescuentoManualAplicado" for n, _ in ev.eventos)


async def test_rol_global_sin_tope_ok():
    venta = await _uc(pct_max=None).ejecutar(
        _input(descuento_total="90", motivo="liquidación", precio="100")
    )
    assert venta.descuento_total == Decimal("90")


async def test_sin_descuento_manual_no_exige_nada():
    venta = await _uc().ejecutar(_input(motivo=None, puede=False))
    assert venta.motivo_descuento is None
