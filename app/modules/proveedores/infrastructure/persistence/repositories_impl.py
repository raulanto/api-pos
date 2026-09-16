from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.responses import Page, PageParams, Sort
from app.modules.proveedores.application.ports.proveedor_repository import ProveedorRepository
from app.modules.proveedores.application.ports.producto_proveedor_repository import (
    ProductoProveedorRepository,
)
from app.modules.proveedores.application.ports.pedido_proveedor_repository import (
    PedidoProveedorRepository,
)
from app.modules.proveedores.application.ports.recepcion_proveedor_repository import (
    RecepcionProveedorRepository,
)
from app.modules.proveedores.application.ports.devolucion_proveedor_repository import (
    DevolucionProveedorRepository,
)
from app.modules.proveedores.application.dtos import (
    FiltroProveedores, FiltroPedidosProveedor, FiltroRecepciones, FiltroDevoluciones,
)
from app.modules.proveedores.domain.entities import (
    Proveedor, ProductoProveedor, PedidoProveedor, RecepcionProveedor,
    RecepcionProveedorLinea, DevolucionProveedor,
)
from app.modules.proveedores.domain.value_objects import EstadoPedidoProveedor
from app.modules.proveedores.infrastructure.persistence.orm_models import (
    ProveedorORM, ProductoProveedorORM, PedidoProveedorORM, PedidoProveedorLineaORM,
    RecepcionProveedorORM, RecepcionProveedorLineaORM, DevolucionProveedorORM,
    DevolucionProveedorLineaORM,
)
from app.modules.proveedores.infrastructure.persistence.mappers import (
    to_domain_proveedor, to_orm_proveedor, to_domain_producto_proveedor,
    to_orm_producto_proveedor, to_domain_pedido, to_orm_pedido,
    to_domain_recepcion, to_orm_recepcion, to_domain_recepcion_linea,
    to_domain_devolucion, to_orm_devolucion,
)


class SqlAlchemyProveedorRepository(ProveedorRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, proveedor_id: UUID) -> Proveedor | None:
        orm = (await self._db.execute(
            select(ProveedorORM).where(ProveedorORM.id == proveedor_id)
        )).scalar_one_or_none()
        return to_domain_proveedor(orm) if orm else None

    async def buscar_por_codigo(self, codigo: str, solo_activos: bool = True) -> Proveedor | None:
        cond = [func.lower(ProveedorORM.codigo) == codigo.strip().lower()]
        if solo_activos:
            cond.append(ProveedorORM.activo.is_(True))
        orm = (await self._db.execute(select(ProveedorORM).where(*cond))).scalars().first()
        return to_domain_proveedor(orm) if orm else None

    async def guardar(self, proveedor: Proveedor) -> None:
        self._db.add(to_orm_proveedor(proveedor))
        await self._db.flush()

    async def actualizar(self, proveedor: Proveedor) -> None:
        await self._db.execute(
            update(ProveedorORM).where(ProveedorORM.id == proveedor.id).values(
                razon_social=proveedor.razon_social, tipo_persona=proveedor.tipo_persona.value,
                condiciones_pago=proveedor.condiciones_pago.value,
                dias_credito=proveedor.dias_credito, moneda=proveedor.moneda,
                nombre_comercial=proveedor.nombre_comercial, rfc=proveedor.rfc,
                contacto_principal=proveedor.contacto_principal, telefono=proveedor.telefono,
                email=proveedor.email, direccion_calle=proveedor.direccion_calle,
                direccion_numero=proveedor.direccion_numero,
                direccion_colonia=proveedor.direccion_colonia,
                direccion_ciudad=proveedor.direccion_ciudad,
                direccion_estado=proveedor.direccion_estado,
                direccion_codigo_postal=proveedor.direccion_codigo_postal,
                activo=proveedor.activo, notas=proveedor.notas,
            )
        )
        await self._db.flush()

    async def listar(self, filtro: FiltroProveedores, paginacion: PageParams, orden: Sort) -> Page:
        cond = []
        if filtro.activo is not None:
            cond.append(ProveedorORM.activo == filtro.activo)
        if filtro.busqueda:
            like = f"%{filtro.busqueda.strip()}%"
            cond.append(
                ProveedorORM.razon_social.ilike(like) | ProveedorORM.codigo.ilike(like)
                | ProveedorORM.rfc.ilike(like)
            )
        col = {"razon_social": ProveedorORM.razon_social, "codigo": ProveedorORM.codigo}.get(
            orden.field, ProveedorORM.razon_social
        )
        orden_expr = col.desc() if orden.descending else col.asc()
        total = await self._db.scalar(select(func.count()).select_from(ProveedorORM).where(*cond))
        filas = (await self._db.execute(
            select(ProveedorORM).where(*cond).order_by(orden_expr)
            .limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_proveedor(o) for o in filas], total=int(total or 0))


class SqlAlchemyProductoProveedorRepository(ProductoProveedorRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, id_: UUID) -> ProductoProveedor | None:
        orm = (await self._db.execute(
            select(ProductoProveedorORM).where(ProductoProveedorORM.id == id_)
        )).scalar_one_or_none()
        return to_domain_producto_proveedor(orm) if orm else None

    async def obtener_por_par(self, producto_id: UUID, proveedor_id: UUID) -> ProductoProveedor | None:
        orm = (await self._db.execute(
            select(ProductoProveedorORM).where(
                ProductoProveedorORM.producto_id == producto_id,
                ProductoProveedorORM.proveedor_id == proveedor_id,
            )
        )).scalar_one_or_none()
        return to_domain_producto_proveedor(orm) if orm else None

    async def guardar(self, pp: ProductoProveedor) -> None:
        self._db.add(to_orm_producto_proveedor(pp))
        await self._db.flush()

    async def actualizar(self, pp: ProductoProveedor) -> None:
        await self._db.execute(
            update(ProductoProveedorORM).where(ProductoProveedorORM.id == pp.id).values(
                codigo_proveedor=pp.codigo_proveedor, precio_compra=pp.precio_compra,
                tiempo_entrega_dias=pp.tiempo_entrega_dias, stock_minimo=pp.stock_minimo,
                stock_maximo=pp.stock_maximo, cantidad_reorden=pp.cantidad_reorden,
                es_proveedor_principal=pp.es_proveedor_principal, activo=pp.activo,
            )
        )
        await self._db.flush()

    async def listar_por_producto(
        self, producto_id: UUID, incluir_inactivos: bool = False,
    ) -> list[ProductoProveedor]:
        cond = [ProductoProveedorORM.producto_id == producto_id]
        if not incluir_inactivos:
            cond.append(ProductoProveedorORM.activo.is_(True))
        filas = (await self._db.execute(select(ProductoProveedorORM).where(*cond))).scalars().all()
        return [to_domain_producto_proveedor(o) for o in filas]

    async def listar_por_proveedor(
        self, proveedor_id: UUID, incluir_inactivos: bool = False,
    ) -> list[ProductoProveedor]:
        cond = [ProductoProveedorORM.proveedor_id == proveedor_id]
        if not incluir_inactivos:
            cond.append(ProductoProveedorORM.activo.is_(True))
        filas = (await self._db.execute(select(ProductoProveedorORM).where(*cond))).scalars().all()
        return [to_domain_producto_proveedor(o) for o in filas]

    async def obtener_principal(self, producto_id: UUID) -> ProductoProveedor | None:
        orm = (await self._db.execute(
            select(ProductoProveedorORM).where(
                ProductoProveedorORM.producto_id == producto_id,
                ProductoProveedorORM.es_proveedor_principal.is_(True),
                ProductoProveedorORM.activo.is_(True),
            )
        )).scalar_one_or_none()
        return to_domain_producto_proveedor(orm) if orm else None

    async def listar_principales_activos(self) -> list[ProductoProveedor]:
        filas = (await self._db.execute(
            select(ProductoProveedorORM).where(
                ProductoProveedorORM.es_proveedor_principal.is_(True),
                ProductoProveedorORM.activo.is_(True),
            )
        )).scalars().all()
        return [to_domain_producto_proveedor(o) for o in filas]


class SqlAlchemyPedidoProveedorRepository(PedidoProveedorRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, pedido_id: UUID, para_actualizar: bool = False) -> PedidoProveedor | None:
        stmt = select(PedidoProveedorORM).where(PedidoProveedorORM.id == pedido_id)
        if para_actualizar:
            stmt = stmt.with_for_update()
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_pedido(orm) if orm else None

    async def obtener_borrador_automatico(
        self, proveedor_id: UUID, sucursal_id: UUID,
    ) -> PedidoProveedor | None:
        orm = (await self._db.execute(
            select(PedidoProveedorORM).where(
                PedidoProveedorORM.proveedor_id == proveedor_id,
                PedidoProveedorORM.sucursal_id == sucursal_id,
                PedidoProveedorORM.estado == EstadoPedidoProveedor.BORRADOR.value,
                PedidoProveedorORM.generado_automaticamente.is_(True),
            ).order_by(PedidoProveedorORM.fecha_pedido.desc())
        )).scalars().first()
        return to_domain_pedido(orm) if orm else None

    async def guardar(self, pedido: PedidoProveedor) -> None:
        self._db.add(to_orm_pedido(pedido))
        await self._db.flush()

    async def actualizar(self, pedido: PedidoProveedor) -> None:
        await self._db.execute(
            update(PedidoProveedorORM).where(PedidoProveedorORM.id == pedido.id).values(
                estado=pedido.estado.value, confirmado_por=pedido.confirmado_por,
                fecha_estimada_entrega=pedido.fecha_estimada_entrega, notas=pedido.notas,
            )
        )
        for l in pedido.lineas:
            existente = await self._db.get(PedidoProveedorLineaORM, l.id)
            if existente is None:
                self._db.add(PedidoProveedorLineaORM(
                    id=l.id, pedido_id=pedido.id, producto_id=l.producto_id,
                    cantidad_solicitada=l.cantidad_solicitada, precio_unitario=l.precio_unitario,
                    cantidad_recibida=l.cantidad_recibida,
                ))
            else:
                existente.cantidad_solicitada = l.cantidad_solicitada
                existente.cantidad_recibida = l.cantidad_recibida
        await self._db.flush()

    async def listar(self, filtro: FiltroPedidosProveedor, paginacion: PageParams, orden: Sort) -> Page:
        cond = []
        if filtro.proveedor_id is not None:
            cond.append(PedidoProveedorORM.proveedor_id == filtro.proveedor_id)
        if filtro.sucursal_id is not None:
            cond.append(PedidoProveedorORM.sucursal_id == filtro.sucursal_id)
        if filtro.estado is not None:
            cond.append(PedidoProveedorORM.estado == filtro.estado.value)
        col = {"fecha_pedido": PedidoProveedorORM.fecha_pedido}.get(
            orden.field, PedidoProveedorORM.fecha_pedido
        )
        orden_expr = col.desc() if orden.descending else col.asc()
        total = await self._db.scalar(select(func.count()).select_from(PedidoProveedorORM).where(*cond))
        filas = (await self._db.execute(
            select(PedidoProveedorORM).options(selectinload(PedidoProveedorORM.lineas))
            .where(*cond).order_by(orden_expr)
            .limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_pedido(o) for o in filas], total=int(total or 0))


class SqlAlchemyRecepcionProveedorRepository(RecepcionProveedorRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, recepcion_id: UUID) -> RecepcionProveedor | None:
        orm = (await self._db.execute(
            select(RecepcionProveedorORM).where(RecepcionProveedorORM.id == recepcion_id)
        )).scalar_one_or_none()
        return to_domain_recepcion(orm) if orm else None

    async def obtener_linea(self, linea_id: UUID) -> RecepcionProveedorLinea | None:
        orm = await self._db.get(RecepcionProveedorLineaORM, linea_id)
        return to_domain_recepcion_linea(orm) if orm else None

    async def guardar(self, recepcion: RecepcionProveedor) -> None:
        self._db.add(to_orm_recepcion(recepcion))
        await self._db.flush()

    async def listar(self, filtro: FiltroRecepciones, paginacion: PageParams, orden: Sort) -> Page:
        cond = []
        if filtro.proveedor_id is not None:
            cond.append(RecepcionProveedorORM.proveedor_id == filtro.proveedor_id)
        if filtro.sucursal_id is not None:
            cond.append(RecepcionProveedorORM.sucursal_id == filtro.sucursal_id)
        if filtro.pedido_id is not None:
            cond.append(RecepcionProveedorORM.pedido_id == filtro.pedido_id)
        col = RecepcionProveedorORM.fecha_recepcion
        orden_expr = col.desc() if orden.descending else col.asc()
        total = await self._db.scalar(select(func.count()).select_from(RecepcionProveedorORM).where(*cond))
        filas = (await self._db.execute(
            select(RecepcionProveedorORM).where(*cond).order_by(orden_expr)
            .limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_recepcion(o) for o in filas], total=int(total or 0))

    async def resumen_defectos_por_proveedor(self, proveedor_id: UUID) -> dict:
        totales = (await self._db.execute(
            select(
                func.coalesce(func.sum(
                    RecepcionProveedorLineaORM.cantidad_recibida_buena
                    + RecepcionProveedorLineaORM.cantidad_defectuosa
                ), 0),
                func.coalesce(func.sum(RecepcionProveedorLineaORM.cantidad_defectuosa), 0),
            )
            .select_from(RecepcionProveedorLineaORM)
            .join(RecepcionProveedorORM, RecepcionProveedorORM.id == RecepcionProveedorLineaORM.recepcion_id)
            .where(RecepcionProveedorORM.proveedor_id == proveedor_id)
        )).first()
        total_recibido, total_defectuoso = totales or (Decimal("0"), Decimal("0"))

        tiempo_real = await self._db.scalar(
            select(func.avg(
                func.extract("epoch", RecepcionProveedorORM.fecha_recepcion - PedidoProveedorORM.fecha_pedido)
                / 86400.0
            ))
            .select_from(RecepcionProveedorORM)
            .join(PedidoProveedorORM, PedidoProveedorORM.id == RecepcionProveedorORM.pedido_id)
            .where(RecepcionProveedorORM.proveedor_id == proveedor_id)
        )
        tiempo_prometido = await self._db.scalar(
            select(func.avg(ProductoProveedorORM.tiempo_entrega_dias)).where(
                ProductoProveedorORM.proveedor_id == proveedor_id,
                ProductoProveedorORM.activo.is_(True),
            )
        )
        return {
            "total_recibido": Decimal(total_recibido or 0),
            "total_defectuoso": Decimal(total_defectuoso or 0),
            "tiempo_real_promedio": Decimal(str(round(tiempo_real, 2))) if tiempo_real is not None else None,
            "tiempo_prometido_promedio": (
                Decimal(str(round(float(tiempo_prometido), 2))) if tiempo_prometido is not None else None
            ),
        }


class SqlAlchemyDevolucionProveedorRepository(DevolucionProveedorRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, devolucion_id: UUID) -> DevolucionProveedor | None:
        orm = (await self._db.execute(
            select(DevolucionProveedorORM).where(DevolucionProveedorORM.id == devolucion_id)
        )).scalar_one_or_none()
        return to_domain_devolucion(orm) if orm else None

    async def guardar(self, devolucion: DevolucionProveedor) -> None:
        self._db.add(to_orm_devolucion(devolucion))
        await self._db.flush()

    async def actualizar(self, devolucion: DevolucionProveedor) -> None:
        await self._db.execute(
            update(DevolucionProveedorORM).where(DevolucionProveedorORM.id == devolucion.id).values(
                estado=devolucion.estado.value,
                resultado=devolucion.resultado.value if devolucion.resultado else None,
                tipo_resolucion=(
                    devolucion.tipo_resolucion.value if devolucion.tipo_resolucion else None
                ),
                fecha_envio=devolucion.fecha_envio, fecha_cierre=devolucion.fecha_cierre,
            )
        )
        await self._db.flush()

    async def cantidad_ya_devuelta(self, recepcion_detalle_id: UUID) -> Decimal:
        total = await self._db.scalar(
            select(func.coalesce(func.sum(DevolucionProveedorLineaORM.cantidad), 0)).where(
                DevolucionProveedorLineaORM.recepcion_detalle_id == recepcion_detalle_id,
            )
        )
        return Decimal(total or 0)

    async def listar(self, filtro: FiltroDevoluciones, paginacion: PageParams, orden: Sort) -> Page:
        cond = []
        if filtro.proveedor_id is not None:
            cond.append(DevolucionProveedorORM.proveedor_id == filtro.proveedor_id)
        if filtro.estado is not None:
            cond.append(DevolucionProveedorORM.estado == filtro.estado.value)
        col = DevolucionProveedorORM.created_at
        orden_expr = col.desc() if orden.descending else col.asc()
        total = await self._db.scalar(select(func.count()).select_from(DevolucionProveedorORM).where(*cond))
        filas = (await self._db.execute(
            select(DevolucionProveedorORM).where(*cond).order_by(orden_expr)
            .limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_devolucion(o) for o in filas], total=int(total or 0))

    async def resumen_por_proveedor(self, proveedor_id: UUID) -> dict:
        filas = (await self._db.execute(
            select(DevolucionProveedorORM.estado, DevolucionProveedorORM.resultado, func.count())
            .where(DevolucionProveedorORM.proveedor_id == proveedor_id)
            .group_by(DevolucionProveedorORM.estado, DevolucionProveedorORM.resultado)
        )).all()
        pendientes = aceptadas = rechazadas = 0
        for estado, resultado, cantidad in filas:
            if estado in ("pendiente", "enviada"):
                pendientes += cantidad
            elif resultado == "aceptada_proveedor":
                aceptadas += cantidad
            elif resultado == "rechazada_proveedor":
                rechazadas += cantidad
        return {"pendientes": pendientes, "aceptadas": aceptadas, "rechazadas": rechazadas}
