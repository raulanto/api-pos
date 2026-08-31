from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reportes.application.ports.reporte_query_port import (
    ReporteQueryPort,
    CorteDeCajaOutput, ReporteVentasOutput, VentasDiaOutput,
    VentasPorMetodoOutput, MetodoPagoTotalOutput,
    VentaPorUsuarioOutput, ProductoRankingOutput,
    InventarioValorizadoOutput, CategoriaValorizadaOutput,
    ClienteSaldoOutput, PaginaReporte,
)
# Lecturas directas de los modelos ORM de otros módulos (patrón CQRS de solo lectura).
from app.modules.ventas.infrastructure.persistence.orm_models import (
    VentaORM, DetalleVentaORM, PagoORM, CajaTurnoORM,
)
from app.modules.ventas.domain.value_objects import MetodoPago, EstadoVenta
from app.modules.inventario.infrastructure.persistence.orm_models import (
    ProductoORM, ExistenciaORM, CategoriaORM,
)
from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM
from app.modules.clientes.infrastructure.persistence.orm_models import ClienteORM

_CERO = Decimal("0")
_CANCELADA = EstadoVenta.CANCELADA.value

# Subtotal de una línea: cantidad * precio - descuento_linea
_LINEA_SUBTOTAL = (
    DetalleVentaORM.cantidad * DetalleVentaORM.precio_unitario - DetalleVentaORM.descuento_linea
)


class SqlAlchemyReporteQueryImpl(ReporteQueryPort):
    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _lineas_por_venta_sq(self):
        """Subconsulta: subtotal (suma de líneas) por venta_id."""
        return (
            select(
                DetalleVentaORM.venta_id.label("venta_id"),
                func.coalesce(func.sum(_LINEA_SUBTOTAL), 0).label("subtotal"),
            )
            .group_by(DetalleVentaORM.venta_id)
            .subquery()
        )

    def _ventas_validas(self, desde: datetime, hasta: datetime, sucursal_id: UUID | None):
        cond = [
            VentaORM.estado != _CANCELADA,
            VentaORM.created_at >= desde,
            VentaORM.created_at <= hasta,
        ]
        if sucursal_id is not None:
            cond.append(VentaORM.sucursal_id == sucursal_id)
        return cond

    # ------------------------------------------------------------------ #
    # Corte de caja (corregido: transferencia separada de tarjeta)
    # ------------------------------------------------------------------ #
    async def calcular_corte_caja(self, caja_turno_id: UUID) -> CorteDeCajaOutput:
        turno = (await self._db.execute(
            select(CajaTurnoORM).where(CajaTurnoORM.id == caja_turno_id)
        )).scalar_one_or_none()
        if not turno:
            raise ValueError(f"CajaTurno {caja_turno_id} no encontrado")

        filas = (await self._db.execute(
            select(PagoORM.metodo_pago, func.coalesce(func.sum(PagoORM.monto), 0))
            .join(VentaORM, VentaORM.id == PagoORM.venta_id)
            .where(VentaORM.caja_turno_id == caja_turno_id, VentaORM.estado != _CANCELADA)
            .group_by(PagoORM.metodo_pago)
        )).all()

        efectivo = tarjeta = transferencia = credito = _CERO
        for metodo, total in filas:
            total = Decimal(total)
            if metodo == MetodoPago.EFECTIVO.value:
                efectivo += total
            elif metodo in (MetodoPago.TARJETA_CREDITO.value, MetodoPago.TARJETA_DEBITO.value):
                tarjeta += total
            elif metodo == MetodoPago.TRANSFERENCIA.value:
                transferencia += total
            elif metodo == MetodoPago.CREDITO.value:
                credito += total

        return CorteDeCajaOutput(
            caja_turno_id=caja_turno_id,
            monto_inicial=turno.saldo_inicial,
            total_efectivo=efectivo,
            total_tarjeta=tarjeta,
            total_transferencia=transferencia,
            total_credito=credito,
            monto_final_esperado=turno.saldo_inicial + efectivo,
        )

    # ------------------------------------------------------------------ #
    # Reporte de ventas por rango
    # ------------------------------------------------------------------ #
    async def reporte_ventas(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None
    ) -> ReporteVentasOutput:
        lineas_sq = self._lineas_por_venta_sq()
        venta_total = func.coalesce(lineas_sq.c.subtotal, 0) - VentaORM.descuento_total
        cond = self._ventas_validas(desde, hasta, sucursal_id)

        totales = (await self._db.execute(
            select(
                func.coalesce(func.sum(venta_total), 0),
                func.count(VentaORM.id),
            )
            .select_from(VentaORM)
            .join(lineas_sq, lineas_sq.c.venta_id == VentaORM.id)
            .where(*cond)
        )).one()
        total_vendido = Decimal(totales[0] or 0)
        numero = int(totales[1] or 0)
        ticket = (total_vendido / numero) if numero else _CERO

        dia = func.date(VentaORM.created_at)
        filas_dia = (await self._db.execute(
            select(dia.label("dia"), func.count(VentaORM.id), func.coalesce(func.sum(venta_total), 0))
            .select_from(VentaORM)
            .join(lineas_sq, lineas_sq.c.venta_id == VentaORM.id)
            .where(*cond)
            .group_by(dia)
            .order_by(dia)
        )).all()

        return ReporteVentasOutput(
            desde=desde, hasta=hasta, sucursal_id=sucursal_id,
            total_vendido=total_vendido, numero_ventas=numero,
            ticket_promedio=ticket.quantize(Decimal("0.01")) if numero else _CERO,
            por_dia=[
                VentasDiaOutput(dia=d, numero_ventas=int(n), total=Decimal(t or 0))
                for d, n, t in filas_dia
            ],
        )

    # ------------------------------------------------------------------ #
    # Ventas por método de pago
    # ------------------------------------------------------------------ #
    async def ventas_por_metodo_pago(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None
    ) -> VentasPorMetodoOutput:
        filas = (await self._db.execute(
            select(PagoORM.metodo_pago, func.coalesce(func.sum(PagoORM.monto), 0))
            .join(VentaORM, VentaORM.id == PagoORM.venta_id)
            .where(*self._ventas_validas(desde, hasta, sucursal_id))
            .group_by(PagoORM.metodo_pago)
        )).all()

        detalle = [MetodoPagoTotalOutput(metodo_pago=m, total=Decimal(t or 0)) for m, t in filas]
        por_metodo = {m: Decimal(t or 0) for m, t in filas}

        efectivo = por_metodo.get(MetodoPago.EFECTIVO.value, _CERO)
        tarjeta = por_metodo.get(MetodoPago.TARJETA_CREDITO.value, _CERO) + \
            por_metodo.get(MetodoPago.TARJETA_DEBITO.value, _CERO)
        transferencia = por_metodo.get(MetodoPago.TRANSFERENCIA.value, _CERO)
        credito = por_metodo.get(MetodoPago.CREDITO.value, _CERO)

        return VentasPorMetodoOutput(
            desde=desde, hasta=hasta, sucursal_id=sucursal_id,
            total_efectivo=efectivo, total_tarjeta=tarjeta,
            total_transferencia=transferencia, total_credito=credito,
            total_general=efectivo + tarjeta + transferencia + credito,
            detalle=detalle,
        )

    # ------------------------------------------------------------------ #
    # Ventas por usuario (cajero)
    # ------------------------------------------------------------------ #
    async def ventas_por_usuario(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> PaginaReporte:
        lineas_sq = self._lineas_por_venta_sq()
        venta_total = func.coalesce(lineas_sq.c.subtotal, 0) - VentaORM.descuento_total
        cond = self._ventas_validas(desde, hasta, sucursal_id)

        total = await self._db.scalar(
            select(func.count(func.distinct(VentaORM.usuario_id)))
            .select_from(VentaORM).where(*cond)
        )
        filas = (await self._db.execute(
            select(
                VentaORM.usuario_id,
                UsuarioORM.nombre,
                func.count(VentaORM.id),
                func.coalesce(func.sum(venta_total), 0),
            )
            .select_from(VentaORM)
            .join(lineas_sq, lineas_sq.c.venta_id == VentaORM.id)
            .join(UsuarioORM, UsuarioORM.id == VentaORM.usuario_id)
            .where(*cond)
            .group_by(VentaORM.usuario_id, UsuarioORM.nombre)
            .order_by(func.coalesce(func.sum(venta_total), 0).desc())
            .limit(limit).offset(offset)
        )).all()

        items = [
            VentaPorUsuarioOutput(
                usuario_id=uid, nombre=nombre,
                numero_ventas=int(n), total_vendido=Decimal(t or 0),
            )
            for uid, nombre, n, t in filas
        ]
        return PaginaReporte(items=items, total=int(total or 0))

    # ------------------------------------------------------------------ #
    # Productos más vendidos
    # ------------------------------------------------------------------ #
    async def top_productos(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None,
        limit: int = 20, offset: int = 0,
    ) -> PaginaReporte:
        cond = self._ventas_validas(desde, hasta, sucursal_id)

        total = await self._db.scalar(
            select(func.count(func.distinct(DetalleVentaORM.producto_id)))
            .select_from(DetalleVentaORM)
            .join(VentaORM, VentaORM.id == DetalleVentaORM.venta_id)
            .where(*cond)
        )
        filas = (await self._db.execute(
            select(
                DetalleVentaORM.producto_id,
                ProductoORM.sku,
                ProductoORM.nombre,
                func.coalesce(func.sum(DetalleVentaORM.cantidad), 0),
                func.coalesce(func.sum(_LINEA_SUBTOTAL), 0),
            )
            .select_from(DetalleVentaORM)
            .join(VentaORM, VentaORM.id == DetalleVentaORM.venta_id)
            .join(ProductoORM, ProductoORM.id == DetalleVentaORM.producto_id)
            .where(*cond)
            .group_by(DetalleVentaORM.producto_id, ProductoORM.sku, ProductoORM.nombre)
            .order_by(func.coalesce(func.sum(DetalleVentaORM.cantidad), 0).desc())
            .limit(limit).offset(offset)
        )).all()

        items = [
            ProductoRankingOutput(
                producto_id=pid, sku=sku, nombre=nombre,
                cantidad_vendida=Decimal(cant or 0), monto_total=Decimal(monto or 0),
            )
            for pid, sku, nombre, cant, monto in filas
        ]
        return PaginaReporte(items=items, total=int(total or 0))

    # ------------------------------------------------------------------ #
    # Inventario valorizado
    # ------------------------------------------------------------------ #
    async def inventario_valorizado(
        self, sucursal_id: UUID | None = None, categoria_id: UUID | None = None
    ) -> InventarioValorizadoOutput:
        valor_expr = func.coalesce(func.sum(ExistenciaORM.cantidad * ProductoORM.costo), 0)
        cond = [ProductoORM.activo.is_(True)]
        if sucursal_id is not None:
            cond.append(ExistenciaORM.sucursal_id == sucursal_id)
        if categoria_id is not None:
            cond.append(ProductoORM.categoria_id == categoria_id)

        filas = (await self._db.execute(
            select(
                CategoriaORM.id,
                CategoriaORM.nombre,
                valor_expr,
                func.count(func.distinct(ProductoORM.id)),
            )
            .select_from(ExistenciaORM)
            .join(ProductoORM, ProductoORM.id == ExistenciaORM.producto_id)
            .join(CategoriaORM, CategoriaORM.id == ProductoORM.categoria_id)
            .where(*cond)
            .group_by(CategoriaORM.id, CategoriaORM.nombre)
            .order_by(valor_expr.desc())
        )).all()

        por_categoria = [
            CategoriaValorizadaOutput(
                categoria_id=cid, nombre=nombre,
                valor=Decimal(valor or 0), numero_productos=int(n or 0),
            )
            for cid, nombre, valor, n in filas
        ]
        return InventarioValorizadoOutput(
            sucursal_id=sucursal_id,
            categoria_id=categoria_id,
            valor_total=sum((c.valor for c in por_categoria), _CERO),
            por_categoria=por_categoria,
        )

    # ------------------------------------------------------------------ #
    # Clientes con saldo de crédito pendiente
    # ------------------------------------------------------------------ #
    async def clientes_con_saldo(
        self, sucursal_id: UUID | None = None, limit: int = 50, offset: int = 0
    ) -> PaginaReporte:
        cond = [ClienteORM.saldo_credito > 0, ClienteORM.activo.is_(True)]
        if sucursal_id is not None:
            cond.append(ClienteORM.sucursal_id == sucursal_id)

        total = await self._db.scalar(
            select(func.count()).select_from(ClienteORM).where(*cond)
        )
        filas = (await self._db.execute(
            select(
                ClienteORM.id, ClienteORM.nombre,
                ClienteORM.saldo_credito, ClienteORM.limite_credito,
            )
            .where(*cond)
            .order_by(ClienteORM.saldo_credito.desc())
            .limit(limit).offset(offset)
        )).all()

        items = [
            ClienteSaldoOutput(
                cliente_id=cid, nombre=nombre,
                saldo_credito=Decimal(saldo or 0), limite_credito=Decimal(limite or 0),
            )
            for cid, nombre, saldo, limite in filas
        ]
        return PaginaReporte(items=items, total=int(total or 0))
