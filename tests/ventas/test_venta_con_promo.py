"""`CrearVentaUseCase` aplica el descuento de promoción y lo congela en la línea."""
import uuid
from decimal import Decimal

from app.modules.ventas.domain.entities import CajaTurno, ESTADO_TURNO_ABIERTO
from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.ventas.application.ports.promociones_port import LineaPromoResult
from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CrearVentaInput, CotizarVentaInput, LineaInput, PagoInput,
)

SUC = uuid.uuid4()
PROD = uuid.uuid4()
TURNO = uuid.uuid4()


class _CajaRepo:
    async def obtener_por_id(self, tid):
        from datetime import datetime, timezone
        return CajaTurno(
            id=tid, sucursal_id=SUC, caja_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
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
    async def precio_mayoreo_aplicable(self, pid, cant):
        return None

    async def convertir_a_base(self, producto_id, cantidad, producto_unidad_id=None):
        return cantidad

    async def stock_disponible(self, producto_id, sucursal_id, producto_unidad_id=None):
        return None

    async def es_servicio(self, producto_id):
        return False

    async def descontar_stock(self, **kw):
        pass


class _Event:
    async def publicar(self, *a, **kw):
        pass


class _PromosPort:
    """Devuelve un 2x1: 1 unidad gratis de la única línea."""
    def __init__(self, descuento):
        self._d = descuento
        self.promo_id = uuid.uuid4()

    async def evaluar(self, sucursal_id, lineas, **kw):
        return [
            LineaPromoResult(
                indice=l.indice, promo_id=self.promo_id,
                promo_etiqueta="2x1", promo_descuento=self._d,
            )
            for l in lineas
        ]


def _input(cantidad="2", precio="50", pago="50"):
    return CrearVentaInput(
        sucursal_id=SUC, caja_turno_id=TURNO, usuario_id=uuid.uuid4(),
        cliente_id=None, descuento_total=Decimal("0"),
        lineas=[LineaInput(producto_id=PROD, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal(precio))],
        pagos=[PagoInput(monto=Decimal(pago), metodo_pago=MetodoPago.EFECTIVO)],
    )


async def test_promo_descuenta_y_se_congela_en_la_linea():
    repo = _VentaRepo()
    uc = CrearVentaUseCase(
        repo, _CajaRepo(), _Inventario(), None, _Event(),
        promociones=_PromosPort(Decimal("50.00")),
    )
    venta = await uc.ejecutar(_input(cantidad="2", precio="50"))
    linea = venta.lineas[0]
    assert linea.promo_etiqueta == "2x1"
    assert linea.promo_descuento == Decimal("50.00")
    # total = 2*50 - 50 (promo) = 50
    assert venta.total == Decimal("50.00")


async def test_sin_promociones_port_comportamiento_intacto():
    repo = _VentaRepo()
    uc = CrearVentaUseCase(repo, _CajaRepo(), _Inventario(), None, _Event())
    venta = await uc.ejecutar(_input(cantidad="2", precio="50", pago="100"))
    assert venta.lineas[0].promo_descuento == Decimal("0")
    assert venta.total == Decimal("100")


async def test_total_promociones_en_la_venta():
    uc = CrearVentaUseCase(
        _VentaRepo(), _CajaRepo(), _Inventario(), None, _Event(),
        promociones=_PromosPort(Decimal("50.00")),
    )
    venta = await uc.ejecutar(_input(cantidad="2", precio="50"))
    assert venta.total_promociones == Decimal("50.00")


async def test_cotizar_no_persiste_ni_exige_turno():
    repo = _VentaRepo()
    uc = CrearVentaUseCase(
        repo, _CajaRepo(), _Inventario(), None, _Event(),
        promociones=_PromosPort(Decimal("50.00")),
    )
    cot = await uc.cotizar(CotizarVentaInput(
        sucursal_id=SUC, descuento_total=Decimal("0"),
        lineas=[LineaInput(producto_id=PROD, cantidad=Decimal("2"),
                           precio_unitario=Decimal("50"))],
    ))
    assert repo.guardada is None                     # no persiste
    assert cot.lineas[0].promo_descuento == Decimal("50.00")
    assert cot.lineas[0].promo_etiqueta == "2x1"
    assert cot.total_promociones == Decimal("50.00")
    assert cot.total == Decimal("50.00")             # 2*50 - 50
