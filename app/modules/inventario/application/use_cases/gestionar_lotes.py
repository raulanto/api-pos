"""Casos de uso del catálogo de lotes (`lote`).

Reglas:
- El producto debe existir y tener `requiere_lote = True`.
- `codigo_lote` único por producto entre lotes activos.
- `costo >= 0`.
- No se puede desactivar un lote con saldo > 0 en alguna sucursal.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import Lote
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, LoteNoEncontrado, LoteDuplicado, LoteInvalido,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.lote_repository import LoteRepository


async def _cargar_producto_con_lote(repo: ProductoRepository, producto_id: UUID):
    producto = await repo.obtener_por_id(producto_id)
    if producto is None:
        raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
    if not producto.requiere_lote:
        raise LoteInvalido(
            f"{producto.nombre} no lleva control por lote. Activá `requiere_lote` primero."
        )
    return producto


class ListarLotesUseCase:
    def __init__(self, lote_repo: LoteRepository, producto_repo: ProductoRepository):
        self._repo = lote_repo
        self._producto_repo = producto_repo

    async def ejecutar(
        self, producto_id: UUID, incluir_inactivos: bool = False
    ) -> list[Lote]:
        if await self._producto_repo.obtener_por_id(producto_id) is None:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
        return await self._repo.listar_por_producto(producto_id, incluir_inactivos)


class ObtenerLoteUseCase:
    def __init__(self, lote_repo: LoteRepository):
        self._repo = lote_repo

    async def ejecutar(self, lote_id: UUID) -> Lote:
        lote = await self._repo.obtener(lote_id)
        if lote is None:
            raise LoteNoEncontrado(f"No existe el lote {lote_id}")
        return lote


@dataclass
class CrearLoteInput:
    producto_id: UUID
    codigo_lote: str
    costo: Decimal
    fecha_caducidad: date | None = None
    proveedor: str | None = None


class CrearLoteUseCase:
    def __init__(self, lote_repo: LoteRepository, producto_repo: ProductoRepository):
        self._repo = lote_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: CrearLoteInput) -> Lote:
        await _cargar_producto_con_lote(self._producto_repo, data.producto_id)
        codigo = data.codigo_lote.strip()
        if await self._repo.obtener_por_codigo(data.producto_id, codigo) is not None:
            raise LoteDuplicado(
                f"Ya existe un lote activo con el código '{codigo}' para este producto."
            )
        lote = Lote.crear(
            producto_id=data.producto_id,
            codigo_lote=codigo,
            costo=data.costo,
            fecha_caducidad=data.fecha_caducidad,
            proveedor=data.proveedor,
        )
        await self._repo.crear(lote)
        return lote


@dataclass
class ActualizarLoteInput:
    lote_id: UUID
    codigo_lote: str | None = None
    fecha_caducidad: date | None = None
    cambiar_fecha_caducidad: bool = False
    costo: Decimal | None = None
    proveedor: str | None = None
    cambiar_proveedor: bool = False


class ActualizarLoteUseCase:
    def __init__(self, lote_repo: LoteRepository):
        self._repo = lote_repo

    async def ejecutar(self, data: ActualizarLoteInput) -> Lote:
        lote = await self._repo.obtener(data.lote_id)
        if lote is None:
            raise LoteNoEncontrado(f"No existe el lote {data.lote_id}")

        if data.codigo_lote is not None and data.codigo_lote.strip() != lote.codigo_lote:
            otro = await self._repo.obtener_por_codigo(lote.producto_id, data.codigo_lote.strip())
            if otro is not None and otro.id != lote.id:
                raise LoteDuplicado(
                    f"Ya existe un lote activo con el código '{data.codigo_lote.strip()}'."
                )

        lote.actualizar(
            codigo_lote=data.codigo_lote,
            fecha_caducidad=data.fecha_caducidad,
            cambiar_fecha_caducidad=data.cambiar_fecha_caducidad,
            costo=data.costo,
            proveedor=data.proveedor,
            cambiar_proveedor=data.cambiar_proveedor,
        )
        await self._repo.actualizar(lote)
        return lote


class DesactivarLoteUseCase:
    def __init__(self, lote_repo: LoteRepository):
        self._repo = lote_repo

    async def ejecutar(self, lote_id: UUID) -> None:
        lote = await self._repo.obtener(lote_id)
        if lote is None:
            raise LoteNoEncontrado(f"No existe el lote {lote_id}")
        saldos = await self._repo.listar_saldos(lote.producto_id, solo_con_saldo=True)
        if any(s.lote_id == lote_id and s.cantidad > 0 for s in saldos):
            raise LoteInvalido(
                "El lote todavía tiene saldo en alguna sucursal; regularizá el stock "
                "(salida / merma / ajuste) antes de desactivarlo."
            )
        lote.desactivar()
        await self._repo.actualizar(lote)


@dataclass
class LoteConSaldo:
    lote: Lote
    sucursal_id: UUID
    cantidad: Decimal
    dias_para_vencer: int | None


class LotesPorVencerUseCase:
    """Lotes con caducidad dentro de `dias` (incluye vencidos), con su saldo por
    sucursal. Para el panel de 'próximos a vencer'."""

    def __init__(self, lote_repo: LoteRepository):
        self._repo = lote_repo

    async def ejecutar(
        self, dias: int = 30, sucursal_ids: list[UUID] | None = None,
    ) -> list[LoteConSaldo]:
        hoy = date.today()
        hasta = hoy + timedelta(days=max(dias, 0))
        filas = await self._repo.por_vencer(hasta, sucursal_ids)
        salida: list[LoteConSaldo] = []
        for lote, sucursal_id, cantidad in filas:
            dpv = (lote.fecha_caducidad - hoy).days if lote.fecha_caducidad else None
            salida.append(LoteConSaldo(lote, sucursal_id, cantidad, dpv))
        return salida
