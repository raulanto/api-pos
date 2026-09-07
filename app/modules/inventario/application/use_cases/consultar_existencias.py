from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import Existencia
from app.modules.inventario.domain.exceptions import ExistenciaNoEncontrada, ProductoNoEncontrado
from app.modules.inventario.application.dtos import FiltroExistencias
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.unidad_repository import ProductoUnidadRepository
from app.shared.responses import Page, PageParams, Sort

_Q = Decimal("0.0001")


@dataclass
class DesglosePresentacion:
    producto_unidad_id: UUID | None   # None = unidad base
    nombre: str
    factor: Decimal
    cantidad: Decimal                 # cantidad_base / factor
    cantidad_entera: int              # floor(cantidad) — "presentaciones completas"


@dataclass
class DesgloseSucursal:
    sucursal_id: UUID
    cantidad_base: Decimal
    stock_minimo: Decimal
    stock_maximo: Decimal | None
    presentaciones: list[DesglosePresentacion]


@dataclass
class DesgloseStock:
    producto_id: UUID
    unidad_base: str
    cantidad_base_global: Decimal
    presentaciones_global: list[DesglosePresentacion]
    por_sucursal: list[DesgloseSucursal]


def _presentaciones(cantidad_base: Decimal, unidad_base: str, unidades) -> list[DesglosePresentacion]:
    # stock nunca es negativo -> int(Decimal) trunca = floor
    filas = [DesglosePresentacion(
        producto_unidad_id=None, nombre=unidad_base, factor=Decimal("1"),
        cantidad=cantidad_base.quantize(_Q), cantidad_entera=int(cantidad_base),
    )]
    for u in unidades:
        if not u.factor or u.factor <= 0:
            continue
        cant = (cantidad_base / u.factor).quantize(_Q)
        filas.append(DesglosePresentacion(
            producto_unidad_id=u.id, nombre=u.nombre, factor=u.factor,
            cantidad=cant, cantidad_entera=int(cant),
        ))
    return filas


class DesglosarStockUseCase:
    """Traduce el saldo (en unidad base) de un producto a cada una de sus
    presentaciones: "8.8750 rejas = 71 botellas". Sólo lectura, sin recalcular
    nada del stock."""

    def __init__(
        self,
        existencia_repo: ExistenciaRepository,
        producto_repo: ProductoRepository,
        unidad_repo: ProductoUnidadRepository,
    ):
        self._repo = existencia_repo
        self._producto_repo = producto_repo
        self._unidad_repo = unidad_repo

    async def ejecutar(
        self, producto_id: UUID, sucursal_ids: list[UUID] | None = None,
    ) -> DesgloseStock:
        producto = await self._producto_repo.obtener_por_id(producto_id)
        if producto is None:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")

        unidades = await self._unidad_repo.listar_por_producto(producto_id)
        existencias = await self._repo.listar(producto_id=producto_id)
        if sucursal_ids:
            existencias = [e for e in existencias if e.sucursal_id in sucursal_ids]

        por_sucursal = [
            DesgloseSucursal(
                sucursal_id=e.sucursal_id,
                cantidad_base=e.cantidad,
                stock_minimo=e.stock_minimo,
                stock_maximo=e.stock_maximo,
                presentaciones=_presentaciones(e.cantidad, producto.unidad_medida, unidades),
            )
            for e in existencias
        ]
        total = sum((e.cantidad for e in existencias), Decimal("0"))
        return DesgloseStock(
            producto_id=producto_id,
            unidad_base=producto.unidad_medida,
            cantidad_base_global=total,
            presentaciones_global=_presentaciones(total, producto.unidad_medida, unidades),
            por_sucursal=por_sucursal,
        )


class ConsultarExistenciasUseCase:
    """Lista existencias paginadas (con o sin filtro `solo_bajo_stock`)."""

    def __init__(self, existencia_repo: ExistenciaRepository):
        self._repo = existencia_repo

    async def ejecutar(
        self,
        filtro: FiltroExistencias,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._repo.buscar(filtro, paginacion, orden, includes)


@dataclass
class ConfigurarUmbralesInput:
    producto_id: UUID
    sucursal_id: UUID
    stock_minimo: Decimal
    stock_maximo: Decimal | None = None


class ConfigurarUmbralesUseCase:
    def __init__(self, existencia_repo: ExistenciaRepository, producto_repo: ProductoRepository):
        self._repo = existencia_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: ConfigurarUmbralesInput) -> Existencia:
        if data.stock_minimo < 0:
            raise ValueError("stock_minimo no puede ser negativo")
        if data.stock_maximo is not None and data.stock_maximo < data.stock_minimo:
            raise ValueError("stock_maximo no puede ser menor que stock_minimo")

        existencia = await self._repo.obtener(data.producto_id, data.sucursal_id)
        if existencia is None:
            # La existencia se crea con el primer movimiento; exigimos que exista
            # para no inventar un registro de stock 0 silenciosamente.
            producto = await self._producto_repo.obtener_por_id(data.producto_id)
            if producto is None:
                raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")
            raise ExistenciaNoEncontrada(
                "No hay registro de existencia para ese producto/sucursal; "
                "registrá primero un movimiento de entrada."
            )

        await self._repo.actualizar_umbrales(
            data.producto_id, data.sucursal_id, data.stock_minimo, data.stock_maximo
        )
        existencia.stock_minimo = data.stock_minimo
        existencia.stock_maximo = data.stock_maximo
        return existencia
