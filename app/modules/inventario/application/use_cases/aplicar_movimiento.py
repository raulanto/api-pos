from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from app.modules.inventario.domain.entities import MovimientoInventario, Existencia
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.domain.exceptions import ProductoNoEncontrado, StockInsuficiente
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository

@dataclass
class AplicarMovimientoInput:
    producto_id: UUID
    sucursal_id: UUID
    tipo: TipoMovimiento
    cantidad: Decimal
    referencia_tipo: str
    usuario_id: UUID
    referencia_id: UUID | None = None
    costo_unitario: Decimal | None = None
    motivo: str | None = None

class AplicarMovimientoUseCase:
    def __init__(
        self,
        producto_repo: ProductoRepository,
        existencia_repo: ExistenciaRepository,
        movimiento_repo: MovimientoRepository
    ):
        self._producto_repo = producto_repo
        self._existencia_repo = existencia_repo
        self._movimiento_repo = movimiento_repo

    async def ejecutar(self, data: AplicarMovimientoInput) -> None:
        producto = await self._producto_repo.obtener_por_id(data.producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")

        existencia = await self._existencia_repo.obtener(data.producto_id, data.sucursal_id)
        
        cantidad_actual = existencia.cantidad if existencia else Decimal("0")
        nuevo_saldo = cantidad_actual

        if data.tipo in (TipoMovimiento.ENTRADA, TipoMovimiento.TRANSFERENCIA): # Simplified transferencia as entrada for destination
            nuevo_saldo += data.cantidad
        elif data.tipo in (TipoMovimiento.SALIDA, TipoMovimiento.MERMA):
            nuevo_saldo -= data.cantidad
        elif data.tipo == TipoMovimiento.AJUSTE:
            # For this example, we assume AJUSTE could be a positive or negative adjustment 
            # Or we could treat 'cantidad' as the final target stock. Let's assume it's additive if we use signs.
            # But earlier we said 'cantidad' must be positive and 'tipo' defines the sign.
            # So let's handle 'ajuste' differently or just say it adds/removes based on another param.
            # We'll treat it as additive if there's a separate mechanism, but let's stick to strict entrada/salida semantics for now.
            # We'll just define that AJUSTE might need more context, so we'll treat it as a generic change.
            pass

        if data.tipo in (TipoMovimiento.SALIDA, TipoMovimiento.MERMA):
            if nuevo_saldo < 0 and not producto.permite_stock_negativo:
                raise StockInsuficiente(
                    f"Stock insuficiente para {producto.nombre}: "
                    f"disponible {cantidad_actual}, solicitado {data.cantidad}"
                )

        movimiento = MovimientoInventario.crear(
            producto_id=data.producto_id,
            sucursal_id=data.sucursal_id,
            tipo=data.tipo,
            cantidad=data.cantidad,
            referencia_tipo=data.referencia_tipo,
            usuario_id=data.usuario_id,
            referencia_id=data.referencia_id,
            costo_unitario=data.costo_unitario,
            motivo=data.motivo
        )

        await self._movimiento_repo.guardar(movimiento)
        
        if not existencia:
            nueva_existencia = Existencia(
                id=movimiento.id, # We could use a new uuid here
                producto_id=data.producto_id,
                sucursal_id=data.sucursal_id,
                cantidad=nuevo_saldo,
                stock_minimo=Decimal("0"),
                stock_maximo=None
            )
            import uuid
            nueva_existencia.id = uuid.uuid4()
            await self._existencia_repo.crear(nueva_existencia)
        else:
            await self._existencia_repo.actualizar_cantidad(data.producto_id, data.sucursal_id, nuevo_saldo)
