from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.usuarios.domain.entities import Usuario
from app.modules.reportes.infrastructure.api.schemas import CorteDeCajaResponse
from app.modules.reportes.application.use_cases.corte_de_caja import CorteDeCajaUseCase
from app.modules.reportes.infrastructure.persistence.reporte_query_impl import SqlAlchemyReporteQueryImpl
from uuid import UUID

router = APIRouter()

def get_corte_caja_use_case(db: AsyncSession = Depends(get_db)) -> CorteDeCajaUseCase:
    return CorteDeCajaUseCase(SqlAlchemyReporteQueryImpl(db))

@router.get("/corte-caja/{caja_turno_id}", response_model=CorteDeCajaResponse)
async def calcular_corte_caja(
    caja_turno_id: UUID,
    use_case: CorteDeCajaUseCase = Depends(get_corte_caja_use_case),
    usuario_actual: Usuario = Depends(get_current_user)
):
    try:
        corte = await use_case.ejecutar(caja_turno_id)
        return corte
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
