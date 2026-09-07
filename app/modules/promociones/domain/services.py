"""Motor de evaluación de promociones. Puro: sin I/O, sin dependencias de infra.

Entrada: las promos candidatas + las líneas del carrito. Salida: cuánto descuenta
cada línea y por qué promo. Reglas:

- Solo promos `vigente_en(momento, sucursal_id)`, ordenadas por `prioridad` asc
  (desempate por `nombre`).
- Una promo por línea como máximo: la primera (por prioridad) que matchee y
  genere descuento > 0 se queda con esa línea.  ponytail: sin apilado; si hiciera
  falta, se iteraría sobre el precio residual.
- NxM agrupa unidades de TODAS las líneas que matchean (cross-line) y regala las
  más baratas.  ponytail: ignora líneas con `cantidad` no entera.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.promociones.domain.entities import Promocion, TipoPromocion

_CENT = Decimal("0.01")


@dataclass
class LineaEval:
    indice: int
    producto_id: UUID
    producto_unidad_id: UUID | None
    cantidad: Decimal
    precio_unitario: Decimal   # ya incluye el mayoreo de unidad base si aplicó


@dataclass
class ResultadoLinea:
    indice: int
    promo_id: UUID | None = None
    promo_etiqueta: str | None = None
    promo_descuento: Decimal = Decimal("0")   # >= 0, cuantizado a 0.01


def evaluar(
    promos: list[Promocion], lineas: list[LineaEval],
    momento: datetime, sucursal_id: UUID,
) -> list[ResultadoLinea]:
    resultados = {l.indice: ResultadoLinea(indice=l.indice) for l in lineas}
    tomadas: set[int] = set()   # índices de línea que ya tienen promo

    candidatas = sorted(
        (p for p in promos if p.vigente_en(momento, sucursal_id)),
        key=lambda p: (p.prioridad, p.nombre),
    )
    for promo in candidatas:
        elegibles = [
            l for l in lineas
            if l.indice not in tomadas
            and any(o.coincide(l.producto_id, l.producto_unidad_id) for o in promo.objetivos)
        ]
        if not elegibles:
            continue
        try:
            descuentos = _descuentos_por_tipo(promo, elegibles)
        except (ArithmeticError, TypeError):
            continue   # promo mal configurada: se omite, no rompe la venta
        for indice, monto in descuentos.items():
            if monto > 0:
                r = resultados[indice]
                r.promo_id = promo.id
                r.promo_etiqueta = promo.nombre
                r.promo_descuento = monto
                tomadas.add(indice)

    return [resultados[l.indice] for l in lineas]


def _descuentos_por_tipo(promo: Promocion, lineas: list[LineaEval]) -> dict[int, Decimal]:
    if promo.tipo == TipoPromocion.PORCENTAJE:
        factor = promo.descuento_pct / Decimal("100")
        return {
            l.indice: (l.cantidad * l.precio_unitario * factor).quantize(_CENT)
            for l in lineas
            if promo.cantidad_minima is None or l.cantidad >= promo.cantidad_minima
        }

    if promo.tipo == TipoPromocion.PRECIO_FIJO:
        out: dict[int, Decimal] = {}
        for l in lineas:
            if promo.cantidad_minima is not None and l.cantidad < promo.cantidad_minima:
                continue
            if promo.precio_fijo < l.precio_unitario:
                out[l.indice] = (
                    l.cantidad * (l.precio_unitario - promo.precio_fijo)
                ).quantize(_CENT)
        return out

    # NxM: pool de unidades enteras de todas las líneas elegibles.
    enteras = [l for l in lineas if l.cantidad == l.cantidad.to_integral_value()]
    total = sum((int(l.cantidad) for l in enteras), 0)
    grupos = total // promo.nxm_lleva
    libres = grupos * (promo.nxm_lleva - promo.nxm_paga)
    if libres <= 0:
        return {}

    out = {}
    for l in sorted(enteras, key=lambda x: x.precio_unitario):
        if libres <= 0:
            break
        n = min(libres, int(l.cantidad))
        out[l.indice] = (Decimal(n) * l.precio_unitario).quantize(_CENT)
        libres -= n
    return out
