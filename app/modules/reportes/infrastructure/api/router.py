from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, Page, PageParams, page_params, ok, page_response,
)
from app.modules.reportes.infrastructure.api.schemas import (
    CorteDeCajaResponse, ReporteVentasResponse, VentasPorMetodoResponse,
    InventarioValorizadoResponse,
    VentaPorUsuarioResponse, ProductoRankingResponse, ClienteSaldoResponse,
)
from app.modules.reportes.infrastructure.persistence.reporte_query_impl import (
    SqlAlchemyReporteQueryImpl,
)
from app.modules.reportes.application.use_cases.corte_de_caja import CorteDeCajaUseCase
from app.modules.reportes.application.use_cases.consultar_reportes import (
    ReporteVentasUseCase, VentasPorMetodoPagoUseCase, VentasPorUsuarioUseCase,
    ProductosMasVendidosUseCase, InventarioValorizadoUseCase, ClientesConSaldoUseCase,
)

router = APIRouter(route_class=EnvelopeRoute)

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


def _filtros_rango(d: datetime, h: datetime, suc: UUID | None) -> dict:
    f = {"desde": d.isoformat(), "hasta": h.isoformat()}
    if suc is not None:
        f["sucursal_id"] = str(suc)
    return f


# ========================================================================== #
@router.get("/corte-caja/{caja_turno_id}", response_model=ApiResponse[CorteDeCajaResponse])
async def calcular_corte_caja(
    caja_turno_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
):
    try:
        corte = await CorteDeCajaUseCase(_q(db)).ejecutar(caja_turno_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    return ok(corte)


@router.get("/ventas", response_model=ApiResponse[ReporteVentasResponse])
async def reporte_ventas(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    return ok(await ReporteVentasUseCase(_q(db)).ejecutar(d, h, suc))


@router.get("/ventas-por-metodo-pago", response_model=ApiResponse[VentasPorMetodoResponse])
async def ventas_por_metodo_pago(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    return ok(await VentasPorMetodoPagoUseCase(_q(db)).ejecutar(d, h, suc))


@router.get("/ventas-por-usuario", response_model=ApiResponse[list[VentaPorUsuarioResponse]])
async def ventas_por_usuario(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    res = await VentasPorUsuarioUseCase(_q(db)).ejecutar(
        d, h, suc, paginacion.limit, paginacion.offset,
    )
    return page_response(
        request, Page(items=res.items, total=res.total), paginacion,
        filters=_filtros_rango(d, h, suc),
    )


@router.get("/productos-mas-vendidos", response_model=ApiResponse[list[ProductoRankingResponse]])
async def productos_mas_vendidos(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
):
    d, h = _rango(desde, hasta)
    suc = _sucursal_reporte(actual, sucursal_id)
    res = await ProductosMasVendidosUseCase(_q(db)).ejecutar(
        d, h, suc, paginacion.limit, paginacion.offset,
    )
    return page_response(
        request, Page(items=res.items, total=res.total), paginacion,
        filters=_filtros_rango(d, h, suc),
    )


@router.get("/inventario-valorizado", response_model=ApiResponse[InventarioValorizadoResponse])
async def inventario_valorizado(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    sucursal_id: UUID | None = Query(default=None),
    categoria_id: UUID | None = Query(default=None),
):
    suc = _sucursal_reporte(actual, sucursal_id)
    return ok(await InventarioValorizadoUseCase(_q(db)).ejecutar(suc, categoria_id))


@router.get("/clientes-con-saldo", response_model=ApiResponse[list[ClienteSaldoResponse]])
async def clientes_con_saldo(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("reportes.leer")),
    sucursal_id: UUID | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
):
    suc = _sucursal_reporte(actual, sucursal_id)
    res = await ClientesConSaldoUseCase(_q(db)).ejecutar(
        suc, paginacion.limit, paginacion.offset,
    )
    return page_response(
        request, Page(items=res.items, total=res.total), paginacion,
        filters={"sucursal_id": str(suc)} if suc else None,
    )
