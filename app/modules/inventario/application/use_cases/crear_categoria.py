from dataclasses import dataclass
from uuid import UUID
from app.modules.inventario.domain.entities import Categoria
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.domain.exceptions import CategoriaNoEncontrada

@dataclass
class CrearCategoriaInput:
    nombre: str
    categoria_padre_id: UUID | None = None

class CrearCategoriaUseCase:
    def __init__(self, categoria_repo: CategoriaRepository):
        self._categoria_repo = categoria_repo

    async def ejecutar(self, data: CrearCategoriaInput) -> Categoria:
        if data.categoria_padre_id:
            padre = await self._categoria_repo.obtener_por_id(data.categoria_padre_id)
            if not padre:
                raise CategoriaNoEncontrada(f"No existe la categoría padre con id {data.categoria_padre_id}")

        categoria = Categoria.crear(nombre=data.nombre, categoria_padre_id=data.categoria_padre_id)
        await self._categoria_repo.guardar(categoria)
        return categoria
