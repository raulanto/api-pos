"""Motor de evaluación de promociones. Puro: sin I/O, sin dependencias de infra.

Entrada: las promos candidatas + las líneas del carrito + el `ContextoEvaluacion`.
Salida: cuánto descuenta cada línea y por qué promo(s). Reglas:

- Solo promos `vigente_en(momento, sucursal_id)` y que cumplan `monto_minimo_compra`
  contra `ctx.total_bruto`.
- **Exclusivas** (`combinable=False`): una por línea. Gana la de menor `prioridad`
  (desempate por `nombre`) que genere descuento > 0. Cierra la línea: no se apila
  nada más encima.
- **Combinables** (`combinable=True`): se apilan sobre el precio residual, en orden
  de `prioridad`, sólo en líneas que no tomó una exclusiva. Cada una acota su
  descuento a su `tope_descuento` y al residual.
- NxM agrupa unidades enteras de TODAS las líneas elegibles (cross-line) y regala
  las más baratas.  ponytail: ignora líneas con `cantidad` no entera; en modo
  combinable "regala la más barata" usa el precio de lista, no el residual.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.modules.promociones.domain.entities import Promocion, TipoPromocion
from app.modules.promociones.domain.value_objects import ContextoEvaluacion

_CENT = Decimal("0.01")


@dataclass
class LineaEval:
    indice: int
    producto_id: UUID
    producto_unidad_id: UUID | None
    cantidad: Decimal
    precio_unitario: Decimal   # ya incluye el mayoreo de unidad base si aplicó
    categoria_id: UUID | None = None   # para objetivos por categoría


@dataclass
class PromoAplicada:
    promo_id: UUID
    etiqueta: str
    monto: Decimal


@dataclass
class ResultadoLinea:
    indice: int
    promo_id: UUID | None = None            # la de mayor monto (compat)
    promo_etiqueta: str | None = None
    promo_descuento: Decimal = Decimal("0")  # Σ de `desglose`, cuantizado a 0.01
    desglose: list[PromoAplicada] = field(default_factory=list)


def _matchea(promo: Promocion, linea: LineaEval) -> bool:
    return any(
        o.coincide(linea.producto_id, linea.producto_unidad_id, linea.categoria_id)
        for o in promo.objetivos
    )


def _acotar(monto: Decimal, tope: Decimal | None, residual: Decimal) -> Decimal:
    tope = monto if tope is None else tope
    return max(Decimal("0"), min(monto, tope, residual)).quantize(_CENT)


def evaluar(
    promos: list[Promocion], lineas: list[LineaEval], ctx: ContextoEvaluacion,
) -> list[ResultadoLinea]:
    resultados = {l.indice: ResultadoLinea(indice=l.indice) for l in lineas}

    vigentes = [
        p for p in promos
        if p.vigente_en(ctx.momento, ctx.sucursal_id)
        and (p.monto_minimo_compra is None or ctx.total_bruto >= p.monto_minimo_compra)
        and (p.metodo_pago_requerido is None or p.metodo_pago_requerido in ctx.metodos_pago)
        and (p.cliente_segmento is None or p.cliente_segmento == ctx.cliente_segmento)
        and (not p.requiere_cupon or p.id in ctx.promos_por_cupon)
    ]
    _orden = lambda p: (p.prioridad, p.nombre)
    exclusivas = sorted((p for p in vigentes if not p.combinable), key=_orden)
    combinables = sorted((p for p in vigentes if p.combinable), key=_orden)

    residual = {l.indice: (l.cantidad * l.precio_unitario) for l in lineas}
    aplicadas: dict[int, list[PromoAplicada]] = {l.indice: [] for l in lineas}
    cerrada: set[int] = set()   # línea tomada por una exclusiva

    # Paso 1 — exclusivas: la primera (por prioridad) que descuente se queda la línea.
    for promo in exclusivas:
        elegibles = [
            l for l in lineas
            if l.indice not in cerrada and not aplicadas[l.indice] and _matchea(promo, l)
        ]
        if not elegibles:
            continue
        try:
            desc = _descuentos_por_tipo(promo, elegibles)
        except (ArithmeticError, TypeError):
            continue   # promo mal configurada: se omite, no rompe la venta
        for indice, monto in desc.items():
            monto = _acotar(monto, promo.tope_descuento, residual[indice])
            if monto > 0:
                aplicadas[indice].append(PromoAplicada(promo.id, promo.nombre, monto))
                residual[indice] -= monto
                cerrada.add(indice)

    # Paso 2 — combinables: apilan sobre el residual, en líneas no cerradas.
    for promo in combinables:
        elegibles = [
            l for l in lineas
            if l.indice not in cerrada and _matchea(promo, l)
        ]
        if not elegibles:
            continue
        try:
            desc = _descuentos_por_tipo(promo, elegibles, base=residual)
        except (ArithmeticError, TypeError):
            continue
        for indice, monto in desc.items():
            monto = _acotar(monto, promo.tope_descuento, residual[indice])
            if monto > 0:
                aplicadas[indice].append(PromoAplicada(promo.id, promo.nombre, monto))
                residual[indice] -= monto

    for l in lineas:
        aps = aplicadas[l.indice]
        if not aps:
            continue
        r = resultados[l.indice]
        r.desglose = aps
        r.promo_descuento = sum((a.monto for a in aps), Decimal("0")).quantize(_CENT)
        principal = max(aps, key=lambda a: a.monto)
        r.promo_id, r.promo_etiqueta = principal.promo_id, principal.etiqueta

    return [resultados[l.indice] for l in lineas]


def _descuentos_por_tipo(
    promo: Promocion, lineas: list[LineaEval],
    base: dict[int, Decimal] | None = None,
) -> dict[int, Decimal]:
    """`base` = monto disponible por línea (residual, para combinables). None =
    `cantidad*precio_unitario` (exclusivas / comportamiento original)."""
    def tope_linea(l: LineaEval) -> Decimal:
        return base[l.indice] if base is not None else (l.cantidad * l.precio_unitario)

    if promo.tipo == TipoPromocion.PORCENTAJE:
        factor = promo.descuento_pct / Decimal("100")
        return {
            l.indice: (tope_linea(l) * factor).quantize(_CENT)
            for l in lineas
            if promo.cantidad_minima is None or l.cantidad >= promo.cantidad_minima
        }

    if promo.tipo == TipoPromocion.PRECIO_FIJO:
        out: dict[int, Decimal] = {}
        for l in lineas:
            if promo.cantidad_minima is not None and l.cantidad < promo.cantidad_minima:
                continue
            if promo.precio_fijo < l.precio_unitario:
                bruto = (
                    l.cantidad * (l.precio_unitario - promo.precio_fijo)
                ).quantize(_CENT)
                out[l.indice] = min(bruto, tope_linea(l))
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
        monto = (Decimal(n) * l.precio_unitario).quantize(_CENT)
        out[l.indice] = min(monto, tope_linea(l))
        libres -= n
    return out
