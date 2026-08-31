from uuid import UUID
from app.modules.reportes.application.ports.reporte_query_port import ReporteQueryPort, CorteDeCajaOutput

class CorteDeCajaUseCase:
    def __init__(self, query_port: ReporteQueryPort):
        self._query = query_port

    async def ejecutar(self, caja_turno_id: UUID) -> CorteDeCajaOutput:
        return await self._query.calcular_corte_caja(caja_turno_id)
