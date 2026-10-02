from decimal import Decimal
from uuid import uuid4
import pytest

from app.modules.inventario.domain.entities import Marca, Producto
from app.modules.inventario.domain.exceptions import (
    MarcaNoEncontrada, MarcaConProductosActivos,
)
from app.modules.inventario.domain.value_objects import TipoProducto
from app.modules.inventario.application.dtos import (
    FiltroMarcas, FiltroProductos,
)
from app.modules.inventario.application.ports.marca_repository import MarcaRepository
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.use_cases.gestionar_marcas import (
    CrearMarcaUseCase, CrearMarcaInput, ListarMarcasUseCase, ObtenerMarcaUseCase,
    ActualizarMarcaUseCase, ActualizarMarcaInput, DesactivarMarcaUseCase, ReactivarMarcaUseCase,
    EliminarMarcaUseCase,
)
from app.modules.inventario.application.use_cases.crear_producto import (
    CrearProductoUseCase, CrearProductoInput,
)
from app.modules.inventario.application.use_cases.gestionar_productos import (
    ActualizarProductoUseCase, ActualizarProductoInput,
)
from app.shared.responses import PageParams, Sort


class InMemoryMarcaRepository(MarcaRepository):
    def __init__(self):
        self.marcas = {}
        self.productos = {}

    async def guardar(self, marca: Marca) -> None:
        self.marcas[marca.id] = marca

    async def actualizar(self, marca: Marca) -> None:
        self.marcas[marca.id] = marca

    async def obtener_por_id(self, marca_id) -> Marca | None:
        return self.marcas.get(marca_id)

    async def listar(self, filtro: FiltroMarcas, paginacion: PageParams, orden: Sort):
        items = list(self.marcas.values())
        if filtro.activo is not None:
            items = [m for m in items if m.activo == filtro.activo]
        if filtro.busqueda:
            items = [m for m in items if filtro.busqueda.lower() in m.nombre.lower()]
        return type("Page", (), {"items": items, "total": len(items)})()

    async def tiene_productos_activos(self, marca_id) -> bool:
        return any(
            p.marca_id == marca_id and p.activo for p in self.productos.values()
        )

    async def eliminar(self, marca_id) -> None:
        self.marcas.pop(marca_id, None)



class InMemoryCategoriaRepository(CategoriaRepository):
    def __init__(self):
        self.cat = type("Cat", (), {"id": uuid4(), "activo": True})()

    async def guardar(self, categoria): pass
    async def actualizar(self, categoria): pass
    async def obtener_por_id(self, categoria_id, includes=frozenset()):
        return self.cat if categoria_id == self.cat.id else None
    async def listar(self, filtro, paginacion, orden, includes=frozenset()): pass
    async def tiene_productos_activos(self, categoria_id): return False


class InMemoryProductoRepository(ProductoRepository):
    def __init__(self, marca_repo):
        self.marca_repo = marca_repo

    async def guardar(self, producto: Producto) -> None:
        self.marca_repo.productos[producto.id] = producto

    async def actualizar(self, producto: Producto) -> None:
        self.marca_repo.productos[producto.id] = producto

    async def obtener_por_id(self, producto_id, includes=frozenset()):
        return self.marca_repo.productos.get(producto_id)

    async def buscar_por_sku(self, sku, solo_activos=True):
        return next((p for p in self.marca_repo.productos.values() if p.sku == sku), None)

    async def buscar_por_codigo_barras(self, cb, solo_activos=True):
        return next((p for p in self.marca_repo.productos.values() if p.codigo_barras == cb), None)

    async def listar(self, filtro, paginacion, orden, includes=frozenset()): pass
    async def kpis(self, filtro): pass
    async def eliminar_fisico(self, producto_id): return []


@pytest.mark.asyncio
async def test_crud_marca():
    marca_repo = InMemoryMarcaRepository()

    # Crear marca
    crear_uc = CrearMarcaUseCase(marca_repo)
    marca = await crear_uc.ejecutar(CrearMarcaInput(nombre="Sony"))
    assert marca.nombre == "Sony"
    assert marca.activo is True

    # Obtener marca
    obtener_uc = ObtenerMarcaUseCase(marca_repo)
    marca_db = await obtener_uc.ejecutar(marca.id)
    assert marca_db.id == marca.id

    # Actualizar marca
    act_uc = ActualizarMarcaUseCase(marca_repo)
    marca_mod = await act_uc.ejecutar(ActualizarMarcaInput(marca_id=marca.id, nombre="Sony Electronics"))
    assert marca_mod.nombre == "Sony Electronics"

    # Desactivar marca
    desact_uc = DesactivarMarcaUseCase(marca_repo)
    marca_des = await desact_uc.ejecutar(marca.id)
    assert marca_des.activo is False

    # Reactivar marca
    react_uc = ReactivarMarcaUseCase(marca_repo)
    marca_react = await react_uc.ejecutar(marca.id)
    assert marca_react.activo is True

    # Eliminar marca
    elim_uc = EliminarMarcaUseCase(marca_repo)
    await elim_uc.ejecutar(marca.id)
    assert await marca_repo.obtener_por_id(marca.id) is None



@pytest.mark.asyncio
async def test_crear_producto_con_marca():
    marca_repo = InMemoryMarcaRepository()
    cat_repo = InMemoryCategoriaRepository()
    prod_repo = InMemoryProductoRepository(marca_repo)

    marca = await CrearMarcaUseCase(marca_repo).ejecutar(CrearMarcaInput(nombre="Nike"))

    uc = CrearProductoUseCase(prod_repo, cat_repo, marca_repo=marca_repo)
    prod = await uc.ejecutar(
        CrearProductoInput(
            sku="NK-001",
            nombre="Zapatillas Nike",
            categoria_id=cat_repo.cat.id,
            marca_id=marca.id,
            unidad_medida="PIEZA",
            precio_venta=Decimal("1200.00"),
            costo=Decimal("800.00"),
            impuesto_tasa=Decimal("16.00"),
        )
    )

    assert prod.marca_id == marca.id

    # No se puede desactivar marca si tiene productos activos
    desact_uc = DesactivarMarcaUseCase(marca_repo)
    with pytest.raises(MarcaConProductosActivos):
        await desact_uc.ejecutar(marca.id)
