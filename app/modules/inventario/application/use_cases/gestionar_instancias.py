"""Casos de uso de la INSTANCIA FÍSICA ABIERTA (envase destapado que se vende en
fracciones de la unidad base).

Contabilidad:
- **Abrir** es neutral: no genera `movimiento_inventario` ni cambia
  `existencia` (los litros siguen físicamente en la tienda); solo crea la fila y
  emite un evento de auditoría.
- **Consumir / Mermar / Descartar / Ajustar** sí generan `movimiento_inventario`
  (SALIDA o MERMA) reutilizando `AplicarMovimientoUseCase`, y bajan el `saldo`
  de la instancia. Cuando el saldo llega a 0 la instancia queda `AGOTADA`.
"""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import InstanciaAbierta
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, ProductoInactivo, UnidadNoEncontrada, LoteInvalido,
    StockInsuficiente,
    InstanciaAbiertaNoEncontrada, ProductoNoRastreaInstancias, InstanciaConfigInvalida,
    CapacidadInstanciaInvalida,
)
from app.modules.inventario.application.dtos import FiltroInstancias
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.unidad_repository import ProductoUnidadRepository
from app.modules.inventario.application.ports.lote_repository import LoteRepository
from app.modules.inventario.application.ports.instancia_abierta_repository import (
    InstanciaAbiertaRepository,
)
from app.modules.inventario.application.ports.event_port import EventPort
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)
from app.shared.responses import Page, PageParams, Sort

EVENTO_ABRIR = "InstanciaAbierta"


async def _resolver_capacidad(
    producto, producto_unidad_id: UUID | None, capacidad: Decimal | None,
    unidad_repo: ProductoUnidadRepository,
) -> Decimal:
    """Capacidad del envase: XOR entre presentación y valor libre; si ninguno,
    el default del producto."""
    if producto_unidad_id is not None and capacidad is not None:
        raise CapacidadInstanciaInvalida(
            "Indicá una presentación O una capacidad manual, no ambas."
        )
    if producto_unidad_id is not None:
        unidad = await unidad_repo.obtener(producto_unidad_id)
        if unidad is None or unidad.producto_id != producto.id:
            raise UnidadNoEncontrada(
                f"La presentación {producto_unidad_id} no es de {producto.id}."
            )
        return unidad.factor
    if capacidad is not None:
        return capacidad
    if producto.instancia_capacidad_default is None:
        raise InstanciaConfigInvalida(
            f"{producto.nombre} no tiene `instancia_capacidad_default`; indicá una "
            "presentación o una capacidad manual."
        )
    return producto.instancia_capacidad_default


# --------------------------------------------------------------------------- #
@dataclass
class AbrirInstanciaInput:
    producto_id: UUID
    sucursal_id: UUID
    usuario_id: UUID
    producto_unidad_id: UUID | None = None
    capacidad: Decimal | None = None
    lote_id: UUID | None = None
    motivo: str | None = None


class AbrirInstanciaUseCase:
    def __init__(
        self,
        producto_repo: ProductoRepository,
        existencia_repo: ExistenciaRepository,
        instancia_repo: InstanciaAbiertaRepository,
        unidad_repo: ProductoUnidadRepository,
        lote_repo: LoteRepository | None = None,
        event_port: EventPort | None = None,
    ):
        self._producto_repo = producto_repo
        self._existencia_repo = existencia_repo
        self._instancia_repo = instancia_repo
        self._unidad_repo = unidad_repo
        self._lote_repo = lote_repo
        self._event_port = event_port

    async def ejecutar(self, data: AbrirInstanciaInput) -> InstanciaAbierta:
        producto = await self._producto_repo.obtener_por_id(data.producto_id)
        if producto is None:
            raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")
        if not producto.activo:
            raise ProductoInactivo(f"El producto {producto.nombre} está inactivo.")
        if not producto.rastrea_instancia_abierta:
            raise ProductoNoRastreaInstancias(
                f"{producto.nombre} no rastrea instancias abiertas."
            )
        if not producto.tipo.mueve_stock:
            raise ProductoNoRastreaInstancias(
                f"{producto.nombre} no mueve inventario."
            )

        capacidad = await _resolver_capacidad(
            producto, data.producto_unidad_id, data.capacidad, self._unidad_repo
        )
        if capacidad <= 0:
            raise CapacidadInstanciaInvalida("La capacidad del envase debe ser > 0.")

        lote_id = await self._resolver_lote(producto, data.sucursal_id, data.lote_id, capacidad)

        # Cobertura de sellado: no se puede abrir más de lo que hay sin abrir.
        existencia = await self._existencia_repo.obtener(data.producto_id, data.sucursal_id)
        total = existencia.cantidad if existencia else Decimal("0")
        abierto = await self._instancia_repo.saldo_abierto(data.producto_id, data.sucursal_id)
        sellado = total - abierto
        if capacidad > sellado and not producto.permite_stock_negativo:
            raise StockInsuficiente(
                f"No hay envase sellado suficiente de {producto.nombre}: sellado "
                f"disponible {sellado}, capacidad pedida {capacidad}."
            )

        instancia = InstanciaAbierta.abrir(
            producto_id=data.producto_id,
            sucursal_id=data.sucursal_id,
            capacidad=capacidad,
            abierta_por=data.usuario_id,
            producto_unidad_id=data.producto_unidad_id,
            lote_id=lote_id,
        )
        await self._instancia_repo.crear(instancia)
        await self._publicar_abrir(instancia, data.motivo)
        return instancia

    async def _resolver_lote(
        self, producto, sucursal_id: UUID, lote_id: UUID | None, capacidad: Decimal,
    ) -> UUID | None:
        if not producto.requiere_lote:
            return None
        if self._lote_repo is None:
            return lote_id
        if lote_id is not None:
            lote = await self._lote_repo.obtener(lote_id)
            if lote is None or lote.producto_id != producto.id:
                raise LoteInvalido(
                    f"El lote {lote_id} no pertenece al producto {producto.id}."
                )
            return lote_id
        # FEFO: primer lote con saldo suficiente para cubrir la capacidad.
        for lid, disp in await self._lote_repo.lotes_fefo(producto.id, sucursal_id):
            if disp >= capacidad:
                return lid
        # Ninguno cubre solo: toma el más FEFO igual (o None si no hay).
        fefo = await self._lote_repo.lotes_fefo(producto.id, sucursal_id)
        return fefo[0][0] if fefo else None

    async def _publicar_abrir(self, instancia: InstanciaAbierta, motivo: str | None) -> None:
        if self._event_port is None:
            return
        await self._event_port.publicar(EVENTO_ABRIR, {
            "usuario_id": instancia.abierta_por,
            "modulo": "inventario",
            "accion": "instancia_abrir",
            "entidad": "InstanciaAbierta",
            "entidad_id": str(instancia.id),
            "detalle": {
                "producto_id": str(instancia.producto_id),
                "sucursal_id": str(instancia.sucursal_id),
                "capacidad": str(instancia.capacidad_inicial),
                "lote_id": str(instancia.lote_id) if instancia.lote_id else None,
                "producto_unidad_id": (
                    str(instancia.producto_unidad_id)
                    if instancia.producto_unidad_id else None
                ),
                "motivo": motivo,
            },
        })


# --------------------------------------------------------------------------- #
class ListarInstanciasUseCase:
    def __init__(self, instancia_repo: InstanciaAbiertaRepository):
        self._repo = instancia_repo

    async def ejecutar(
        self, filtro: FiltroInstancias, paginacion: PageParams, orden: Sort,
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


class ObtenerInstanciaUseCase:
    def __init__(self, instancia_repo: InstanciaAbiertaRepository):
        self._repo = instancia_repo

    async def ejecutar(self, instancia_id: UUID) -> InstanciaAbierta:
        instancia = await self._repo.obtener(instancia_id)
        if instancia is None:
            raise InstanciaAbiertaNoEncontrada(f"No existe la instancia {instancia_id}")
        return instancia


# --------------------------------------------------------------------------- #
# Operaciones que consumen saldo (todas generan movimiento_inventario).
# --------------------------------------------------------------------------- #
async def _mover_y_consumir(
    instancia: InstanciaAbierta,
    cantidad: Decimal,
    tipo: TipoMovimiento,
    referencia_tipo: str,
    usuario_id: UUID,
    motivo: str | None,
    motor: AplicarMovimientoUseCase,
    instancia_repo: InstanciaAbiertaRepository,
    referencia_id: UUID | None = None,
) -> None:
    """Registra un SALIDA/MERMA por `cantidad` contra el producto/sucursal/lote
    de la instancia, y baja su saldo. `instancia.consumir` valida saldo y estado."""
    instancia.consumir(cantidad, motivo=motivo or "agotada")
    await motor.ejecutar(AplicarMovimientoInput(
        producto_id=instancia.producto_id,
        sucursal_id=instancia.sucursal_id,
        tipo=tipo,
        cantidad=cantidad,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        usuario_id=usuario_id,
        motivo=motivo,
        lote_id=instancia.lote_id,
        instancia_abierta_id=instancia.id,
    ))
    await instancia_repo.actualizar(instancia)


@dataclass
class ConsumirInstanciaInput:
    instancia_id: UUID
    cantidad: Decimal
    usuario_id: UUID
    motivo: str | None = None
    referencia_tipo: str = "consumo_instancia"
    referencia_id: UUID | None = None


class ConsumirInstanciaUseCase:
    """Dispensa una fracción de un envase abierto (uso interno / mostrador)."""

    def __init__(
        self, instancia_repo: InstanciaAbiertaRepository, motor: AplicarMovimientoUseCase,
    ):
        self._repo = instancia_repo
        self._motor = motor

    async def ejecutar(self, data: ConsumirInstanciaInput) -> InstanciaAbierta:
        instancia = await _cargar(self._repo, data.instancia_id)
        await _mover_y_consumir(
            instancia, data.cantidad, TipoMovimiento.SALIDA, data.referencia_tipo,
            data.usuario_id, data.motivo, self._motor, self._repo, data.referencia_id,
        )
        return instancia


@dataclass
class MermarInstanciaInput:
    instancia_id: UUID
    cantidad: Decimal
    usuario_id: UUID
    motivo: str | None = None


class MermarInstanciaUseCase:
    def __init__(
        self, instancia_repo: InstanciaAbiertaRepository, motor: AplicarMovimientoUseCase,
    ):
        self._repo = instancia_repo
        self._motor = motor

    async def ejecutar(self, data: MermarInstanciaInput) -> InstanciaAbierta:
        instancia = await _cargar(self._repo, data.instancia_id)
        await _mover_y_consumir(
            instancia, data.cantidad, TipoMovimiento.MERMA, "merma_instancia",
            data.usuario_id, data.motivo or "merma", self._motor, self._repo,
        )
        return instancia


@dataclass
class DescartarInstanciaInput:
    instancia_id: UUID
    usuario_id: UUID
    motivo: str


class DescartarInstanciaUseCase:
    """Da de baja el envase con su remanente: MERMA de todo el saldo + DESCARTADA."""

    def __init__(
        self, instancia_repo: InstanciaAbiertaRepository, motor: AplicarMovimientoUseCase,
    ):
        self._repo = instancia_repo
        self._motor = motor

    async def ejecutar(self, data: DescartarInstanciaInput) -> InstanciaAbierta:
        instancia = await _cargar(self._repo, data.instancia_id)
        remanente = instancia.descartar(data.motivo)
        if remanente > 0:
            await self._motor.ejecutar(AplicarMovimientoInput(
                producto_id=instancia.producto_id,
                sucursal_id=instancia.sucursal_id,
                tipo=TipoMovimiento.MERMA,
                cantidad=remanente,
                referencia_tipo="descarte_instancia",
                usuario_id=data.usuario_id,
                motivo=data.motivo,
                lote_id=instancia.lote_id,
                instancia_abierta_id=instancia.id,
            ))
        await self._repo.actualizar(instancia)
        return instancia


@dataclass
class AjustarInstanciaInput:
    instancia_id: UUID
    saldo_medido: Decimal
    usuario_id: UUID
    motivo: str | None = None


class AjustarInstanciaUseCase:
    """Concilia el saldo con una medición física. Solo baja: si la medición
    supera el saldo registrado -> `CapacidadInstanciaInvalida` (abrir otra
    instancia, no inflar esta)."""

    def __init__(
        self, instancia_repo: InstanciaAbiertaRepository, motor: AplicarMovimientoUseCase,
    ):
        self._repo = instancia_repo
        self._motor = motor

    async def ejecutar(self, data: AjustarInstanciaInput) -> InstanciaAbierta:
        instancia = await _cargar(self._repo, data.instancia_id)
        if data.saldo_medido < 0:
            raise CapacidadInstanciaInvalida("La medición no puede ser negativa.")
        delta = data.saldo_medido - instancia.saldo
        if delta > 0:
            raise CapacidadInstanciaInvalida(
                "La medición supera el saldo registrado del envase; si hay más "
                "producto, abrí otra instancia."
            )
        if delta < 0:
            await _mover_y_consumir(
                instancia, -delta, TipoMovimiento.MERMA, "ajuste_instancia",
                data.usuario_id, data.motivo or "ajuste por conteo",
                self._motor, self._repo,
            )
        return instancia


async def _cargar(
    repo: InstanciaAbiertaRepository, instancia_id: UUID,
) -> InstanciaAbierta:
    instancia = await repo.obtener(instancia_id)
    if instancia is None:
        raise InstanciaAbiertaNoEncontrada(f"No existe la instancia {instancia_id}")
    return instancia
