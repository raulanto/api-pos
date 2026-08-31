from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado, verificar_alcance_sucursal
from app.modules.inventario.application.dtos import FiltroMovimientos, Paginacion
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.application.use_cases.listar_movimientos import (
    ListarMovimientosUseCase, ObtenerMovimientoUseCase,
)
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)
from app.modules.inventario.application.use_cases.transferir_stock import (
    TransferirStockUseCase, TransferirStockInput,
)
from app.modules.inventario.infrastructure.adapters.event_port_impl import EventPortImpl
from app.modules.inventario.infrastructure.api.schemas import (
    AplicarMovimientoRequest, TransferenciaRequest, MovimientoResponse, MovimientosPaginados,
)
from .common import mov_repo, prod_repo, exist_repo, sucursal_efectiva, traducir

router = APIRouter()

"""
    Endpoint para aplicar movimientos.

    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase dict.
"""
@router.post("/movimientos", status_code=status.HTTP_201_CREATED)
async def aplicar_movimiento(
    body: AplicarMovimientoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    if not actual.sucursal_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada")
    if body.tipo == TipoMovimiento.TRANSFERENCIA:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Usá POST /movimientos/transferencia para transferencias entre sucursales.",
        )

    use_case = AplicarMovimientoUseCase(
        prod_repo(db), exist_repo(db), mov_repo(db), EventPortImpl(db)
    )
    try:
        await use_case.ejecutar(AplicarMovimientoInput(
            producto_id=body.producto_id,
            sucursal_id=actual.sucursal_id,
            tipo=body.tipo,
            referencia_tipo=body.referencia_tipo,
            usuario_id=actual.id,
            cantidad=body.cantidad,
            cantidad_final=body.cantidad_final,
            referencia_id=body.referencia_id,
            costo_unitario=body.costo_unitario,
            motivo=body.motivo,
            stock_minimo=body.stock_minimo,
            stock_maximo=body.stock_maximo,
        ))
    except Exception as e:
        raise traducir(e)
    return {"status": "ok"}


"""
    Endpoint para transferir stock.

    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase dict.
"""
@router.post("/movimientos/transferencia", status_code=status.HTTP_201_CREATED)
async def transferir_stock(
    body: TransferenciaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    # Un usuario no global sólo puede sacar stock de su propia sucursal.
    verificar_alcance_sucursal(actual, body.sucursal_origen_id)

    use_case = TransferirStockUseCase(
        prod_repo(db), exist_repo(db), mov_repo(db), EventPortImpl(db)
    )
    try:
        await use_case.ejecutar(TransferirStockInput(
            producto_id=body.producto_id,
            sucursal_origen_id=body.sucursal_origen_id,
            sucursal_destino_id=body.sucursal_destino_id,
            cantidad=body.cantidad,
            usuario_id=actual.id,
            referencia_id=body.referencia_id,
            costo_unitario=body.costo_unitario,
            motivo=body.motivo,
        ))
    except Exception as e:
        raise traducir(e)
    return {"status": "ok"}

"""
    Endpoint para listar movimientos.

    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param producto_id: ID del producto.
    @param sucursal_id: ID de la sucursal.
    @param tipo: Tipo de movimiento.
    @param desde: Fecha desde.
    @param hasta: Fecha hasta.
    @param limit: Límite de resultados.
    @param offset: Desplazamiento de resultados.
    @return: Instancia de la clase MovimientosPaginados.
"""
@router.get("/movimientos", response_model=MovimientosPaginados)
async def listar_movimientos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    producto_id: UUID | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    tipo: TipoMovimiento | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    efectivo = sucursal_efectiva(actual, sucursal_id)
    pagina = await ListarMovimientosUseCase(mov_repo(db)).ejecutar(
        FiltroMovimientos(
            producto_id=producto_id, sucursal_id=efectivo, tipo=tipo, desde=desde, hasta=hasta,
        ),
        Paginacion(limit=limit, offset=offset),
    )
    return MovimientosPaginados(items=pagina.items, total=pagina.total, limit=limit, offset=offset)

"""
    Endpoint para obtener un movimiento.

    @param movimiento_id: ID del movimiento.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase MovimientoResponse.
"""
@router.get("/movimientos/{movimiento_id}", response_model=MovimientoResponse)
async def obtener_movimiento(
    movimiento_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        movimiento = await ObtenerMovimientoUseCase(mov_repo(db)).ejecutar(movimiento_id)
    except Exception as e:
        raise traducir(e)
    verificar_alcance_sucursal(actual, movimiento.sucursal_id)
    return movimiento
