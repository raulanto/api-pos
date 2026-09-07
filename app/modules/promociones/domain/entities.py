from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from app.modules.promociones.domain.exceptions import PromocionInvalida


class TipoPromocion(str, Enum):
    NXM = "nxm"                # 2x1, 3x2, NxM
    PORCENTAJE = "porcentaje"  # % de descuento sobre la línea
    PRECIO_FIJO = "precio_fijo"  # precio unitario forzado (mayoreo por presentación)


@dataclass
class PromocionObjetivo:
    """Un producto (a unidad base) o una presentación concreta al que aplica la
    promoción. Exactamente uno de los dos ids va poblado."""
    id: UUID
    promocion_id: UUID
    producto_id: UUID | None = None
    producto_unidad_id: UUID | None = None

    def coincide(self, producto_id: UUID, producto_unidad_id: UUID | None) -> bool:
        if self.producto_unidad_id is not None:
            return self.producto_unidad_id == producto_unidad_id
        if self.producto_id is not None:
            return self.producto_id == producto_id and producto_unidad_id is None
        return False


@dataclass
class Promocion:
    """Campaña de descuento configurable. `prioridad` menor = se evalúa primero y
    gana la línea (una promo por línea, sin apilar)."""
    id: UUID
    nombre: str
    tipo: TipoPromocion
    activo: bool = True
    prioridad: int = 100
    sucursal_id: UUID | None = None          # None = todas las sucursales
    vigente_desde: datetime | None = None
    vigente_hasta: datetime | None = None
    # Params por tipo (solo el del `tipo` correspondiente va poblado):
    nxm_lleva: int | None = None
    nxm_paga: int | None = None
    descuento_pct: Decimal | None = None
    precio_fijo: Decimal | None = None
    cantidad_minima: Decimal | None = None   # umbral para PRECIO_FIJO / PORCENTAJE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    objetivos: list[PromocionObjetivo] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # `_validar` corre en `crear()` / `actualizar()`, NO al hidratar desde la BD
    # (una fila persistida ya pasó por acá; volver a validarla solo la haría
    # frágil ante datos históricos).
    def _validar(self) -> None:
        if not self.objetivos:
            raise PromocionInvalida("La promoción necesita al menos un producto o presentación objetivo.")
        if self.prioridad < 0:
            raise PromocionInvalida("`prioridad` no puede ser negativa.")
        if (
            self.vigente_desde is not None
            and self.vigente_hasta is not None
            and self.vigente_hasta < self.vigente_desde
        ):
            raise PromocionInvalida("`vigente_hasta` no puede ser anterior a `vigente_desde`.")

        if self.tipo == TipoPromocion.NXM:
            if self.nxm_lleva is None or self.nxm_paga is None:
                raise PromocionInvalida("NxM requiere `nxm_lleva` y `nxm_paga`.")
            if not (self.nxm_lleva > self.nxm_paga > 0):
                raise PromocionInvalida("NxM debe cumplir `nxm_lleva > nxm_paga > 0`.")
        elif self.tipo == TipoPromocion.PORCENTAJE:
            if self.descuento_pct is None or not (Decimal("0") < self.descuento_pct <= Decimal("100")):
                raise PromocionInvalida("`descuento_pct` debe estar en (0, 100].")
        elif self.tipo == TipoPromocion.PRECIO_FIJO:
            if self.precio_fijo is None or self.precio_fijo < 0:
                raise PromocionInvalida("`precio_fijo` debe ser >= 0.")

        if self.cantidad_minima is not None and self.cantidad_minima <= 0:
            raise PromocionInvalida("`cantidad_minima` debe ser > 0.")

    # ------------------------------------------------------------------ #
    @staticmethod
    def crear(
        nombre: str, tipo: TipoPromocion, objetivos: list[PromocionObjetivo],
        prioridad: int = 100, activo: bool = True, sucursal_id: UUID | None = None,
        vigente_desde: datetime | None = None, vigente_hasta: datetime | None = None,
        nxm_lleva: int | None = None, nxm_paga: int | None = None,
        descuento_pct: Decimal | None = None, precio_fijo: Decimal | None = None,
        cantidad_minima: Decimal | None = None,
    ) -> "Promocion":
        pid = uuid4()
        for o in objetivos:
            o.promocion_id = pid
        promo = Promocion(
            id=pid, nombre=nombre.strip(), tipo=tipo, activo=activo,
            prioridad=prioridad, sucursal_id=sucursal_id,
            vigente_desde=vigente_desde, vigente_hasta=vigente_hasta,
            nxm_lleva=nxm_lleva, nxm_paga=nxm_paga, descuento_pct=descuento_pct,
            precio_fijo=precio_fijo, cantidad_minima=cantidad_minima,
            objetivos=objetivos,
        )
        promo._validar()
        return promo

    def actualizar(
        self,
        nombre: str | None = None, prioridad: int | None = None,
        activo: bool | None = None,
        sucursal_id: UUID | None = None, cambiar_sucursal: bool = False,
        vigente_desde: datetime | None = None, vigente_hasta: datetime | None = None,
        cambiar_vigencia: bool = False,
        tipo: TipoPromocion | None = None,
        nxm_lleva: int | None = None, nxm_paga: int | None = None,
        descuento_pct: Decimal | None = None, precio_fijo: Decimal | None = None,
        cantidad_minima: Decimal | None = None, cambiar_cantidad_minima: bool = False,
        objetivos: list[PromocionObjetivo] | None = None,
    ) -> None:
        if nombre is not None:
            self.nombre = nombre.strip()
        if prioridad is not None:
            self.prioridad = prioridad
        if activo is not None:
            self.activo = activo
        if cambiar_sucursal:
            self.sucursal_id = sucursal_id
        if cambiar_vigencia:
            self.vigente_desde = vigente_desde
            self.vigente_hasta = vigente_hasta
        if tipo is not None:
            self.tipo = tipo
        if nxm_lleva is not None:
            self.nxm_lleva = nxm_lleva
        if nxm_paga is not None:
            self.nxm_paga = nxm_paga
        if descuento_pct is not None:
            self.descuento_pct = descuento_pct
        if precio_fijo is not None:
            self.precio_fijo = precio_fijo
        if cambiar_cantidad_minima:
            self.cantidad_minima = cantidad_minima
        elif cantidad_minima is not None:
            self.cantidad_minima = cantidad_minima
        if objetivos is not None:
            for o in objetivos:
                o.promocion_id = self.id
            self.objetivos = objetivos
        self._validar()

    def activar(self) -> None:
        self.activo = True

    def desactivar(self) -> None:
        self.activo = False

    # ------------------------------------------------------------------ #
    def vigente_en(self, momento: datetime, sucursal_id: UUID) -> bool:
        return (
            self.activo
            and (self.vigente_desde is None or self.vigente_desde <= momento)
            and (self.vigente_hasta is None or momento <= self.vigente_hasta)
            and (self.sucursal_id is None or self.sucursal_id == sucursal_id)
        )
