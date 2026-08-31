from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.usuarios.domain.entities import Usuario
from app.modules.ventas.infrastructure.api.schemas import CrearVentaRequest, VentaResponse
from app.modules.ventas.application.use_cases.crear_venta import CrearVentaUseCase, CrearVentaInput, LineaInput, PagoInput
from app.modules.ventas.infrastructure.persistence.repositories_impl import SqlAlchemyVentaRepository, SqlAlchemyCajaTurnoRepository
from app.modules.clientes.infrastructure.persistence.cliente_repository_impl import SqlAlchemyClienteRepository
from app.modules.ventas.infrastructure.adapters.inventario_port_impl import InventarioPortImpl
from app.modules.ventas.domain.exceptions import CajaNoAbierta, VentaCreditoSinCliente, VentaSinLineas
from app.modules.clientes.domain.exceptions import LimiteCreditoExcedido
from app.modules.inventario.domain.exceptions import StockInsuficiente

router = APIRouter()

def get_crear_venta_use_case(db: AsyncSession = Depends(get_db)) -> CrearVentaUseCase:
    return CrearVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        caja_repo=SqlAlchemyCajaTurnoRepository(db),
        inventario=InventarioPortImpl(db),
        cliente_repo=SqlAlchemyClienteRepository(db)
    )

@router.post("/", response_model=VentaResponse, status_code=status.HTTP_201_CREATED)
async def crear_venta(
    body: CrearVentaRequest,
    use_case: CrearVentaUseCase = Depends(get_crear_venta_use_case),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if not usuario_actual.sucursal_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada")

    input_data = CrearVentaInput(
        sucursal_id=usuario_actual.sucursal_id,
        caja_turno_id=body.caja_turno_id,
        usuario_id=usuario_actual.id,
        cliente_id=body.cliente_id,
        descuento_total=body.descuento_total,
        lineas=[
            LineaInput(
                producto_id=l.producto_id,
                cantidad=l.cantidad,
                precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa
            ) for l in body.lineas
        ],
        pagos=[
            PagoInput(monto=p.monto, metodo_pago=p.metodo_pago)
            for p in body.pagos
        ]
    )

    try:
        # Note: exceptions will bubble up and AsyncSession commit won't be called if they happen
        # Router Exception handler in app.core.exceptions will catch these domain exceptions if we have them mapped,
        # otherwise we can map them here
        venta = await use_case.ejecutar(input_data)
        return venta
    except CajaNoAbierta as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (VentaCreditoSinCliente, LimiteCreditoExcedido, VentaSinLineas, StockInsuficiente) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
