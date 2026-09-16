from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.proveedores.domain.entities import DevolucionProveedor, DevolucionProveedorLinea
from app.modules.proveedores.domain.value_objects import ResultadoDevolucion, TipoResolucionDevolucion
from app.modules.proveedores.domain.exceptions import (
    DevolucionProveedorNoEncontrada, RecepcionProveedorNoEncontrada,
    CantidadDevolucionExcedeDefecto,
)
from app.modules.proveedores.application.ports.devolucion_proveedor_repository import (
    DevolucionProveedorRepository,
)
from app.modules.proveedores.application.ports.recepcion_proveedor_repository import (
    RecepcionProveedorRepository,
)
from app.modules.proveedores.application.dtos import FiltroDevoluciones
from app.shared.responses import Page, PageParams, Sort


@dataclass
class LineaDevolucionInput:
    recepcion_detalle_id: UUID
    cantidad: Decimal


@dataclass
class CrearDevolucionInput:
    proveedor_id: UUID
    recepcion_id: UUID
    creado_por: UUID
    lineas: list[LineaDevolucionInput]
    notas: str | None = None


class CrearDevolucionUseCase:
    def __init__(
        self, repo: DevolucionProveedorRepository, recepcion_repo: RecepcionProveedorRepository,
    ):
        self._repo = repo
        self._recepcion_repo = recepcion_repo

    async def ejecutar(self, data: CrearDevolucionInput) -> DevolucionProveedor:
        lineas: list[DevolucionProveedorLinea] = []
        for l in data.lineas:
            detalle = await self._recepcion_repo.obtener_linea(l.recepcion_detalle_id)
            if detalle is None:
                raise RecepcionProveedorNoEncontrada(
                    f"No existe la línea de recepción {l.recepcion_detalle_id}"
                )
            ya_devuelto = await self._repo.cantidad_ya_devuelta(l.recepcion_detalle_id)
            if ya_devuelto + l.cantidad > detalle.cantidad_defectuosa:
                raise CantidadDevolucionExcedeDefecto(
                    f"La línea permite devolver {detalle.cantidad_defectuosa - ya_devuelto} "
                    f"más; pediste {l.cantidad}."
                )
            lineas.append(DevolucionProveedorLinea.crear(
                recepcion_detalle_id=l.recepcion_detalle_id, producto_id=detalle.producto_id,
                cantidad=l.cantidad,
            ))
        devolucion = DevolucionProveedor.crear(
            proveedor_id=data.proveedor_id, recepcion_id=data.recepcion_id,
            creado_por=data.creado_por, lineas=lineas, notas=data.notas,
        )
        await self._repo.guardar(devolucion)
        return devolucion


async def _cargar(repo: DevolucionProveedorRepository, devolucion_id: UUID) -> DevolucionProveedor:
    devolucion = await repo.obtener_por_id(devolucion_id)
    if devolucion is None:
        raise DevolucionProveedorNoEncontrada(f"No existe la devolución {devolucion_id}")
    return devolucion


class EnviarDevolucionUseCase:
    def __init__(self, repo: DevolucionProveedorRepository):
        self._repo = repo

    async def ejecutar(self, devolucion_id: UUID) -> DevolucionProveedor:
        devolucion = await _cargar(self._repo, devolucion_id)
        devolucion.enviar()
        await self._repo.actualizar(devolucion)
        return devolucion


class CerrarDevolucionUseCase:
    def __init__(self, repo: DevolucionProveedorRepository):
        self._repo = repo

    async def ejecutar(
        self, devolucion_id: UUID, resultado: ResultadoDevolucion,
        tipo_resolucion: TipoResolucionDevolucion | None = None,
    ) -> DevolucionProveedor:
        devolucion = await _cargar(self._repo, devolucion_id)
        devolucion.cerrar(resultado, tipo_resolucion)
        await self._repo.actualizar(devolucion)
        return devolucion


class ObtenerDevolucionUseCase:
    def __init__(self, repo: DevolucionProveedorRepository):
        self._repo = repo

    async def ejecutar(self, devolucion_id: UUID) -> DevolucionProveedor:
        return await _cargar(self._repo, devolucion_id)


class ListarDevolucionesUseCase:
    def __init__(self, repo: DevolucionProveedorRepository):
        self._repo = repo

    async def ejecutar(self, filtro: FiltroDevoluciones, paginacion: PageParams, orden: Sort) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)
