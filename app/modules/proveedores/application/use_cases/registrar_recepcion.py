from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.modules.proveedores.domain.entities import RecepcionProveedor, RecepcionProveedorLinea
from app.modules.proveedores.domain.value_objects import MotivoDefecto, AccionDefecto
from app.modules.proveedores.domain.exceptions import RecepcionProveedorNoEncontrada
from app.modules.proveedores.application.ports.recepcion_proveedor_repository import (
    RecepcionProveedorRepository,
)
from app.modules.proveedores.application.ports.pedido_proveedor_repository import (
    PedidoProveedorRepository,
)
from app.modules.proveedores.application.dtos import FiltroRecepciones
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.shared.responses import Page, PageParams, Sort

REFERENCIA_ENTRADA = "recepcion_proveedor"
REFERENCIA_MERMA = "recepcion_proveedor_defecto"


@dataclass
class LineaRecepcionInput:
    producto_id: UUID
    cantidad_recibida_buena: Decimal
    cantidad_defectuosa: Decimal = Decimal("0")
    cantidad_esperada: Decimal | None = None
    motivo_defecto: MotivoDefecto | None = None
    accion_defecto: AccionDefecto | None = None
    fotos_evidencia_keys: list[str] = field(default_factory=list)
    notas: str | None = None


@dataclass
class RegistrarRecepcionInput:
    proveedor_id: UUID
    sucursal_id: UUID
    recibido_por: UUID
    lineas: list[LineaRecepcionInput]
    pedido_id: UUID | None = None
    numero_factura: str | None = None
    numero_remision: str | None = None
    transportista: str | None = None
    notas: str | None = None


class RegistrarRecepcionUseCase:
    """Crea la recepción (evento inmutable) y aplica sus efectos en la misma
    transacción: ENTRADA por lo bueno, MERMA por lo defectuoso marcado
    `accion_defecto=merma`, y actualiza `cantidad_recibida` del pedido si
    venía uno. Si algo falla (ej. stock/lote inválido), `get_db()` revierte
    todo — no queda una recepción a medias."""

    def __init__(
        self,
        recepcion_repo: RecepcionProveedorRepository,
        pedido_repo: PedidoProveedorRepository,
        aplicar_movimiento: AplicarMovimientoUseCase,
    ):
        self._recepcion_repo = recepcion_repo
        self._pedido_repo = pedido_repo
        self._aplicar_movimiento = aplicar_movimiento

    async def ejecutar(self, data: RegistrarRecepcionInput) -> RecepcionProveedor:
        lineas = [
            RecepcionProveedorLinea.crear(
                producto_id=l.producto_id,
                cantidad_recibida_buena=l.cantidad_recibida_buena,
                cantidad_defectuosa=l.cantidad_defectuosa,
                cantidad_esperada=l.cantidad_esperada,
                motivo_defecto=l.motivo_defecto, accion_defecto=l.accion_defecto,
                fotos_evidencia_keys=l.fotos_evidencia_keys, notas=l.notas,
            )
            for l in data.lineas
        ]
        recepcion = RecepcionProveedor.crear(
            proveedor_id=data.proveedor_id, sucursal_id=data.sucursal_id,
            recibido_por=data.recibido_por, lineas=lineas, pedido_id=data.pedido_id,
            numero_factura=data.numero_factura, numero_remision=data.numero_remision,
            transportista=data.transportista, notas=data.notas,
        )
        await self._recepcion_repo.guardar(recepcion)

        for linea in recepcion.lineas:
            if linea.cantidad_recibida_buena > 0:
                await self._aplicar_movimiento.ejecutar(AplicarMovimientoInput(
                    producto_id=linea.producto_id, sucursal_id=data.sucursal_id,
                    tipo=TipoMovimiento.ENTRADA, referencia_tipo=REFERENCIA_ENTRADA,
                    referencia_id=recepcion.id, usuario_id=data.recibido_por,
                    cantidad=linea.cantidad_recibida_buena,
                ))
            if linea.cantidad_defectuosa > 0 and linea.accion_defecto == AccionDefecto.MERMA:
                await self._aplicar_movimiento.ejecutar(AplicarMovimientoInput(
                    producto_id=linea.producto_id, sucursal_id=data.sucursal_id,
                    tipo=TipoMovimiento.MERMA, referencia_tipo=REFERENCIA_MERMA,
                    referencia_id=recepcion.id, usuario_id=data.recibido_por,
                    cantidad=linea.cantidad_defectuosa,
                    motivo=f"Defecto de recepción: {linea.motivo_defecto.value}",
                ))

        if data.pedido_id is not None:
            pedido = await self._pedido_repo.obtener_por_id(data.pedido_id, para_actualizar=True)
            if pedido is not None:
                por_producto: dict[UUID, Decimal] = {}
                for linea in recepcion.lineas:
                    por_producto[linea.producto_id] = (
                        por_producto.get(linea.producto_id, Decimal("0"))
                        + linea.cantidad_recibida_buena
                    )
                pedido.registrar_recepcion_parcial(por_producto)
                await self._pedido_repo.actualizar(pedido)

        return recepcion


class ObtenerRecepcionUseCase:
    def __init__(self, repo: RecepcionProveedorRepository):
        self._repo = repo

    async def ejecutar(self, recepcion_id: UUID) -> RecepcionProveedor:
        recepcion = await self._repo.obtener_por_id(recepcion_id)
        if recepcion is None:
            raise RecepcionProveedorNoEncontrada(f"No existe la recepción {recepcion_id}")
        return recepcion


class ListarRecepcionesUseCase:
    def __init__(self, repo: RecepcionProveedorRepository):
        self._repo = repo

    async def ejecutar(self, filtro: FiltroRecepciones, paginacion: PageParams, orden: Sort) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)
