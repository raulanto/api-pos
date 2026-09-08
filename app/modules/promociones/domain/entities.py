from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.modules.promociones.domain.exceptions import PromocionInvalida, CuponVencido


def _local(momento: datetime) -> datetime:
    """`momento` (UTC o naive-asumido-UTC) a la zona horaria del negocio."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    try:
        return momento.astimezone(ZoneInfo(settings.app_timezone))
    except Exception:
        return momento.astimezone(timezone.utc)


class TipoPromocion(str, Enum):
    NXM = "nxm"                # 2x1, 3x2, NxM
    PORCENTAJE = "porcentaje"  # % de descuento sobre la línea
    PRECIO_FIJO = "precio_fijo"  # precio unitario forzado (mayoreo por presentación)


@dataclass
class PromocionObjetivo:
    """A qué aplica la promoción: un producto (unidad base), una presentación
    concreta, o una categoría. Exactamente uno de los tres ids va poblado."""
    id: UUID
    promocion_id: UUID
    producto_id: UUID | None = None
    producto_unidad_id: UUID | None = None
    categoria_id: UUID | None = None

    def coincide(
        self, producto_id: UUID, producto_unidad_id: UUID | None,
        categoria_id: UUID | None = None,
    ) -> bool:
        if self.categoria_id is not None:
            return categoria_id is not None and self.categoria_id == categoria_id
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
    # Sucursales donde aplica; lista vacía = todas.
    sucursales: list[UUID] = field(default_factory=list)
    vigente_desde: datetime | None = None
    vigente_hasta: datetime | None = None
    # Ventana horaria y días de la semana (hora local del negocio). `dias_semana`
    # es un bitmask lun..dom = bit 0..6; None = todos los días.
    hora_desde: time | None = None
    hora_hasta: time | None = None
    dias_semana: int | None = None
    # Apilado: `combinable=False` (default) = exclusiva por línea; `True` = se
    # apila sobre el residual junto a otras combinables.
    combinable: bool = False
    # Tope de descuento por línea que esta promo puede aplicar (None = sin tope).
    tope_descuento: Decimal | None = None
    # La promo sólo aplica si el total bruto de la venta alcanza este monto.
    monto_minimo_compra: Decimal | None = None
    # Condición: sólo aplica si algún pago usa este método (None = cualquiera).
    metodo_pago_requerido: str | None = None
    # Condición: sólo aplica si el cliente de la venta tiene este segmento.
    cliente_segmento: str | None = None
    # Si True, la promo NO entra en `listar_vigentes` salvo que un cupón válido
    # la habilite (ver módulo cupones).
    requiere_cupon: bool = False
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
            # NxM cuenta unidades por línea; mezclar unidad base y presentación
            # de distinto factor haría un pool sin sentido.
            tiene_prod = any(o.producto_id is not None for o in self.objetivos)
            tiene_pres = any(o.producto_unidad_id is not None for o in self.objetivos)
            if tiene_prod and tiene_pres:
                raise PromocionInvalida(
                    "Una promo NxM no puede mezclar la unidad base y una "
                    "presentación; creá una promo por cada una."
                )
        elif self.tipo == TipoPromocion.PORCENTAJE:
            if self.descuento_pct is None or not (Decimal("0") < self.descuento_pct <= Decimal("100")):
                raise PromocionInvalida("`descuento_pct` debe estar en (0, 100].")
        elif self.tipo == TipoPromocion.PRECIO_FIJO:
            if self.precio_fijo is None or self.precio_fijo < 0:
                raise PromocionInvalida("`precio_fijo` debe ser >= 0.")

        if self.cantidad_minima is not None and self.cantidad_minima <= 0:
            raise PromocionInvalida("`cantidad_minima` debe ser > 0.")
        if self.tope_descuento is not None and self.tope_descuento < 0:
            raise PromocionInvalida("`tope_descuento` no puede ser negativo.")
        if self.monto_minimo_compra is not None and self.monto_minimo_compra < 0:
            raise PromocionInvalida("`monto_minimo_compra` no puede ser negativo.")
        if self.dias_semana is not None and not (1 <= self.dias_semana <= 127):
            raise PromocionInvalida("`dias_semana` (bitmask lun..dom) debe estar en [1, 127].")
        if (self.hora_desde is None) != (self.hora_hasta is None):
            raise PromocionInvalida("`hora_desde` y `hora_hasta` van juntas o ninguna.")

    # ------------------------------------------------------------------ #
    @staticmethod
    def crear(
        nombre: str, tipo: TipoPromocion, objetivos: list[PromocionObjetivo],
        prioridad: int = 100, activo: bool = True,
        sucursales: list[UUID] | None = None,
        vigente_desde: datetime | None = None, vigente_hasta: datetime | None = None,
        hora_desde: time | None = None, hora_hasta: time | None = None,
        dias_semana: int | None = None,
        nxm_lleva: int | None = None, nxm_paga: int | None = None,
        descuento_pct: Decimal | None = None, precio_fijo: Decimal | None = None,
        cantidad_minima: Decimal | None = None,
        combinable: bool = False, tope_descuento: Decimal | None = None,
        monto_minimo_compra: Decimal | None = None,
        metodo_pago_requerido: str | None = None,
        cliente_segmento: str | None = None,
        requiere_cupon: bool = False,
    ) -> "Promocion":
        pid = uuid4()
        for o in objetivos:
            o.promocion_id = pid
        promo = Promocion(
            id=pid, nombre=nombre.strip(), tipo=tipo, activo=activo,
            prioridad=prioridad, sucursales=list(sucursales or []),
            vigente_desde=vigente_desde, vigente_hasta=vigente_hasta,
            hora_desde=hora_desde, hora_hasta=hora_hasta, dias_semana=dias_semana,
            combinable=combinable, tope_descuento=tope_descuento,
            monto_minimo_compra=monto_minimo_compra,
            metodo_pago_requerido=metodo_pago_requerido,
            cliente_segmento=cliente_segmento, requiere_cupon=requiere_cupon,
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
        sucursales: list[UUID] | None = None, cambiar_sucursales: bool = False,
        vigente_desde: datetime | None = None, vigente_hasta: datetime | None = None,
        cambiar_vigencia: bool = False,
        hora_desde: time | None = None, hora_hasta: time | None = None,
        dias_semana: int | None = None, cambiar_horario: bool = False,
        tipo: TipoPromocion | None = None,
        combinable: bool | None = None,
        tope_descuento: Decimal | None = None,
        monto_minimo_compra: Decimal | None = None,
        cambiar_topes: bool = False,
        metodo_pago_requerido: str | None = None,
        cliente_segmento: str | None = None,
        requiere_cupon: bool | None = None,
        cambiar_condiciones: bool = False,
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
        if combinable is not None:
            self.combinable = combinable
        if cambiar_topes:
            self.tope_descuento = tope_descuento
            self.monto_minimo_compra = monto_minimo_compra
        if cambiar_condiciones:
            self.metodo_pago_requerido = metodo_pago_requerido
            self.cliente_segmento = cliente_segmento
            if requiere_cupon is not None:
                self.requiere_cupon = requiere_cupon
        elif requiere_cupon is not None:
            self.requiere_cupon = requiere_cupon
        if cambiar_sucursales:
            self.sucursales = list(sucursales or [])
        if cambiar_vigencia:
            self.vigente_desde = vigente_desde
            self.vigente_hasta = vigente_hasta
        if cambiar_horario:
            self.hora_desde = hora_desde
            self.hora_hasta = hora_hasta
            self.dias_semana = dias_semana
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
        if not (
            self.activo
            and (self.vigente_desde is None or self.vigente_desde <= momento)
            and (self.vigente_hasta is None or momento <= self.vigente_hasta)
            and (not self.sucursales or sucursal_id in self.sucursales)
        ):
            return False
        if self.dias_semana is None and self.hora_desde is None:
            return True
        loc = _local(momento)
        if self.dias_semana is not None and not (self.dias_semana >> loc.weekday()) & 1:
            return False
        if self.hora_desde is not None:
            t = loc.time()
            if self.hora_desde <= self.hora_hasta:
                if not (self.hora_desde <= t <= self.hora_hasta):
                    return False
            else:  # cruza medianoche (ej. 22:00 -> 02:00)
                if not (t >= self.hora_desde or t <= self.hora_hasta):
                    return False
        return True


# --------------------------------------------------------------------------- #
# Cupones
# --------------------------------------------------------------------------- #
@dataclass
class Cupon:
    """Código que habilita una promoción (`promocion.requiere_cupon = True`),
    con su propia vigencia y límites de uso."""
    id: UUID
    codigo: str
    promocion_id: UUID
    activo: bool = True
    vigente_desde: datetime | None = None
    vigente_hasta: datetime | None = None
    max_usos_total: int | None = None
    max_usos_por_persona: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def crear(codigo: str, promocion_id: UUID, **kw) -> "Cupon":
        c = (codigo or "").strip().upper()
        if not c:
            raise PromocionInvalida("El código del cupón es obligatorio.")
        if kw.get("max_usos_total") is not None and kw["max_usos_total"] <= 0:
            raise PromocionInvalida("`max_usos_total` debe ser > 0.")
        if kw.get("max_usos_por_persona") is not None and kw["max_usos_por_persona"] <= 0:
            raise PromocionInvalida("`max_usos_por_persona` debe ser > 0.")
        return Cupon(id=uuid4(), codigo=c, promocion_id=promocion_id, **kw)

    def vigente_en(self, momento: datetime) -> bool:
        return (
            self.activo
            and (self.vigente_desde is None or self.vigente_desde <= momento)
            and (self.vigente_hasta is None or momento <= self.vigente_hasta)
        )

    def exigir_vigente(self, momento: datetime) -> None:
        if not self.vigente_en(momento):
            raise CuponVencido(f"El cupón {self.codigo} no está vigente.")


@dataclass
class CuponUso:
    id: UUID
    cupon_id: UUID
    venta_id: UUID
    monto_descontado: Decimal
    telefono: str | None = None
    cliente_id: UUID | None = None
    usado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def crear(cupon_id: UUID, venta_id: UUID, monto_descontado: Decimal,
              telefono: str | None = None, cliente_id: UUID | None = None) -> "CuponUso":
        return CuponUso(
            id=uuid4(), cupon_id=cupon_id, venta_id=venta_id,
            monto_descontado=monto_descontado, telefono=telefono, cliente_id=cliente_id,
        )
