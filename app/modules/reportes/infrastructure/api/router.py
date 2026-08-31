from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.modules.reportes.infrastructure.api.schemas import (
    CorteDeCajaResponse, ReporteVentasResponse, VentasPorMetodoResponse,
    InventarioValorizadoResponse, ProductosMasVendidosResponse,
    VentasPorUsuarioResponse, ClientesConSaldoResponse,
)
from app.modules.reportes.infrastructure.persistence.reporte_query_impl import (
    SqlAlchemyReporteQueryImpl,
)
from app.modules.reportes.application.use_cases.corte_de_caja import CorteDeCajaUseCase
from app.modules.reportes.application.use_cases.consultar_reportes import (
    ReporteVentasUseCase, VentasPorMetodoPagoUseCase, VentasPorUsuarioUseCase,
    ProductosMasVendidosUseCase, InventarioValorizadoUseCase, ClientesConSaldoUseCase,
)

router = APIRouter()

# Rango por defecto cuando no se especifican fechas (evita escanear toda la tabla).
_RANGO_DEFECTO_DIAS = 365


def _q(db: AsyncSession) -> SqlAlchemyReporteQueryImpl:
    return SqlAlchemyReporteQueryImpl(db)


def _rango(desde: datetime | None, hasta: datetime | None) -> tuple[datetime, datetime]:
    hasta = hasta or datetime.utcnow()
    desde = desde or (hasta - timedelta(days=_RANGO_DEFECTO_DIAS))
    if desde > hasta:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="`desde` no puede ser mayor que `hasta`")
    return desde, hasta


def _sucursal_reporte(actual: UsuarioAutenticado, pedida: UUID | None) -> UUID | None:
    """Roles globales (admin/gerente) eligen sucursal o ven todas (None).
    El resto queda forzado a su propia sucursal, ignora `pedida`."""
    if actual.ve_todas_las_sucursales:
        return pedida
    if not actual.sucursal_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada"
        )
    return actual.sucursal_id


# ========================================================================== #
@router.get("/corte-caja/{caja_turno_id}", response_model=CorteDeCajaResponse)
async def calcular_corte_caja(
    caja_turno_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
):
    try:
        return await CorteDeCajaUseCase(_q(db)).ejecutar(caja_turno_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/ventas", response_model=ReporteVentasResponse)
async def reporte_ventas(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    return await ReporteVentasUseCase(_q(db)).ejecutar(d, h, suc)


@router.get("/ventas-por-metodo-pago", response_model=VentasPorMetodoResponse)
async def ventas_por_metodo_pago(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    return await VentasPorMetodoPagoUseCase(_q(db)).ejecutar(d, h, suc)


@router.get("/ventas-por-usuario", response_model=VentasPorUsuarioResponse)
async def ventas_por_usuario(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    pagina = await VentasPorUsuarioUseCase(_q(db)).ejecutar(d, h, suc, limit, offset)
    return VentasPorUsuarioResponse(items=pagina.items, total=pagina.total, limit=limit, offset=offset)


@router.get("/productos-mas-vendidos", response_model=ProductosMasVendidosResponse)
async def productos_mas_vendidos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200, description="Top N productos"),
    offset: int = Query(default=0, ge=0),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    pagina = await ProductosMasVendidosUseCase(_q(db)).ejecutar(d, h, suc, limit, offset)
    return ProductosMasVendidosResponse(items=pagina.items, total=pagina.total, limit=limit, offset=offset)


@router.get("/inventario-valorizado", response_model=InventarioValorizadoResponse)
async def inventario_valorizado(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    sucursal_id: UUID | None = Query(default=None),
    categoria_id: UUID | None = Query(default=None),
):
    suc = _sucursal_reporte(actual, sucursal_id)
    return await InventarioValorizadoUseCase(_q(db)).ejecutar(suc, categoria_id)


@router.get("/clientes-con-saldo", response_model=ClientesConSaldoResponse)
async def clientes_con_saldo(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    sucursal_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    suc = _sucursal_reporte(actual, sucursal_id)
    pagina = await ClientesConSaldoUseCase(_q(db)).ejecutar(suc, limit, offset)
    return ClientesConSaldoResponse(items=pagina.items, total=pagina.total, limit=limit, offset=offset)
