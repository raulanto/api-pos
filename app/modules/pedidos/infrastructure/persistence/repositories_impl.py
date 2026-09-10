from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.pedidos.application.dtos import FiltroPedidos
from app.modules.pedidos.application.ports.pedido_repository import PedidoRepository
from app.modules.pedidos.domain.entities import Pedido, PedidoPago
from app.modules.pedidos.infrastructure.persistence.mappers import (
    to_orm_pedido, to_domain_pedido, _det_to_orm, _pago_to_orm,
)
from app.modules.pedidos.infrastructure.persistence.orm_models import (
    PedidoORM, PedidoPagoORM,
)
from app.shared.responses import Page, PageParams, Sort

# Escrituras hacen `flush`, nunca `commit`: la transacción la cierra get_db().


class SqlAlchemyPedidoRepository(PedidoRepository):
    _ORDEN = {"created_at": PedidoORM.created_at, "fecha_promesa": PedidoORM.fecha_promesa}

    def __init__(self, db: AsyncSession):
        self._db = db

    def _opts(self):
        return [selectinload(PedidoORM.lineas), selectinload(PedidoORM.pagos)]

    async def guardar(self, pedido: Pedido) -> None:
        self._db.add(to_orm_pedido(pedido))
        await self._db.flush()

    async def actualizar(self, pedido: Pedido) -> None:
        orm = (await self._db.execute(
            select(PedidoORM).options(selectinload(PedidoORM.lineas))
            .where(PedidoORM.id == pedido.id)
        )).scalar_one()
        orm.cliente_id = pedido.cliente_id
        orm.tipo = pedido.tipo.value
        orm.canal = pedido.canal.value
        orm.estado = pedido.estado.value
        orm.estado_entrega = pedido.estado_entrega.value if pedido.estado_entrega else None
        orm.telefono = pedido.telefono
        orm.descuento_total = pedido.descuento_total
        orm.motivo_descuento = pedido.motivo_descuento
        orm.costo_envio = pedido.costo_envio
        orm.codigo_cupon = pedido.codigo_cupon
        orm.cliente_segmento = pedido.cliente_segmento
        orm.notas = pedido.notas
        orm.fecha_promesa = pedido.fecha_promesa
        orm.direccion_texto = pedido.direccion_texto
        orm.referencia_direccion = pedido.referencia_direccion
        orm.repartidor_id = pedido.repartidor_id
        orm.entrega_fallo_motivo = pedido.entrega_fallo_motivo
        orm.despachado_en = pedido.despachado_en
        orm.entregado_en = pedido.entregado_en
        orm.venta_id = pedido.venta_id
        # Reemplaza las líneas (pueden haber cambiado tras re-cotizar). El cascade
        # `delete-orphan` borra las que salen. ponytail: siempre reescribe las N
        # líneas aunque no cambien; son pocas, no vale la pena diferenciar.
        for l in pedido.lineas:
            l.pedido_id = pedido.id
        orm.lineas = [_det_to_orm(l) for l in pedido.lineas]
        await self._db.flush()

    async def agregar_pago(self, pago: PedidoPago) -> None:
        self._db.add(_pago_to_orm(pago))
        await self._db.flush()

    async def marcar_pagos_reembolsados(self, pedido_id: UUID) -> None:
        await self._db.execute(
            update(PedidoPagoORM)
            .where(PedidoPagoORM.pedido_id == pedido_id,
                   PedidoPagoORM.reembolsado.is_(False))
            .values(reembolsado=True)
        )
        await self._db.flush()

    async def obtener_por_id(
        self, pedido_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Pedido | None:
        orm = (await self._db.execute(
            select(PedidoORM).options(*self._opts()).where(PedidoORM.id == pedido_id)
        )).scalar_one_or_none()
        return to_domain_pedido(orm) if orm else None

    async def obtener_por_idempotency_key(self, key: str) -> Pedido | None:
        orm = (await self._db.execute(
            select(PedidoORM).options(*self._opts())
            .where(PedidoORM.idempotency_key == key)
        )).scalar_one_or_none()
        return to_domain_pedido(orm) if orm else None

    async def listar(
        self, filtro: FiltroPedidos, paginacion: PageParams, orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        cond = []
        if filtro.sucursal_id is not None:
            cond.append(PedidoORM.sucursal_id == filtro.sucursal_id)
        if filtro.cliente_id is not None:
            cond.append(PedidoORM.cliente_id == filtro.cliente_id)
        if filtro.repartidor_id is not None:
            cond.append(PedidoORM.repartidor_id == filtro.repartidor_id)
        if filtro.telefono is not None:
            cond.append(PedidoORM.telefono == filtro.telefono.strip())
        if filtro.tipo is not None:
            cond.append(PedidoORM.tipo == filtro.tipo.value)
        if filtro.canal is not None:
            cond.append(PedidoORM.canal == filtro.canal.value)
        if filtro.estado is not None:
            cond.append(PedidoORM.estado == filtro.estado.value)
        if filtro.estado_entrega is not None:
            cond.append(PedidoORM.estado_entrega == filtro.estado_entrega.value)
        if filtro.desde is not None:
            cond.append(PedidoORM.created_at >= filtro.desde)
        if filtro.hasta is not None:
            cond.append(PedidoORM.created_at <= filtro.hasta)

        col = self._ORDEN.get(orden.field, PedidoORM.created_at)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(PedidoORM).where(*cond)
        )
        filas = (await self._db.execute(
            select(PedidoORM).options(*self._opts()).where(*cond)
            .order_by(orden_expr).limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_pedido(o) for o in filas], total=int(total or 0))

    async def contar_por_estado(self, sucursal_id: UUID | None) -> dict[str, int]:
        return await self._contar(PedidoORM.estado, sucursal_id)

    async def contar_por_estado_entrega(self, sucursal_id: UUID | None) -> dict[str, int]:
        return await self._contar(PedidoORM.estado_entrega, sucursal_id)

    async def _contar(self, col, sucursal_id: UUID | None) -> dict[str, int]:
        cond = [col.isnot(None)]
        if sucursal_id is not None:
            cond.append(PedidoORM.sucursal_id == sucursal_id)
        filas = (await self._db.execute(
            select(col, func.count()).where(*cond).group_by(col)
        )).all()
        return {k: int(v) for k, v in filas}
