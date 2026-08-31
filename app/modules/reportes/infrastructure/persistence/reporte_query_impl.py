from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.modules.reportes.application.ports.reporte_query_port import ReporteQueryPort, CorteDeCajaOutput
from app.modules.ventas.infrastructure.persistence.orm_models import VentaORM, PagoORM, CajaTurnoORM
from app.modules.ventas.domain.value_objects import MetodoPago

class SqlAlchemyReporteQueryImpl(ReporteQueryPort):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def calcular_corte_caja(self, caja_turno_id: UUID) -> CorteDeCajaOutput:
        # Obtener caja_turno
        stmt_turno = select(CajaTurnoORM).where(CajaTurnoORM.id == caja_turno_id)
        result_turno = await self._db.execute(stmt_turno)
        turno = result_turno.scalar_one_or_none()
        
        if not turno:
            raise ValueError(f"CajaTurno {caja_turno_id} no encontrado")

        monto_inicial = turno.saldo_inicial

        # Obtener sumas agrupadas por metodo_pago de ventas no canceladas
        stmt_pagos = (
            select(
                PagoORM.metodo_pago,
                func.sum(PagoORM.monto).label("total")
            )
            .join(VentaORM, PagoORM.venta_id == VentaORM.id)
            .where(
                VentaORM.caja_turno_id == caja_turno_id,
                VentaORM.estado != "cancelada"
            )
            .group_by(PagoORM.metodo_pago)
        )
        
        result_pagos = await self._db.execute(stmt_pagos)
        pagos_agrupados = result_pagos.all()

        total_efectivo = Decimal("0")
        total_tarjeta = Decimal("0")
        total_credito = Decimal("0")

        for metodo, total in pagos_agrupados:
            if metodo == MetodoPago.EFECTIVO.value:
                total_efectivo += total
            elif metodo in [MetodoPago.TARJETA_CREDITO.value, MetodoPago.TARJETA_DEBITO.value]:
                total_tarjeta += total
            elif metodo == MetodoPago.CREDITO.value:
                total_credito += total
            elif metodo == MetodoPago.TRANSFERENCIA.value:
                # Se puede agrupar en otro lado o en tarjeta
                total_tarjeta += total

        monto_final_esperado = monto_inicial + total_efectivo

        return CorteDeCajaOutput(
            caja_turno_id=caja_turno_id,
            monto_inicial=monto_inicial,
            total_efectivo=total_efectivo,
            total_tarjeta=total_tarjeta,
            total_credito=total_credito,
            monto_final_esperado=monto_final_esperado
        )
