from dataclasses import dataclass, field
from uuid import UUID, uuid4


"""
Clase que representa una categoría en el inventario.
Permite crear, actualizar y desactivar categorías.
"""
@dataclass
class Categoria:
    id: UUID
    nombre: str
    categoria_padre_id: UUID | None
    activo: bool

    # Relación embebida opcional (`?include=padre`); la puebla el mapper.
    padre: object | None = field(default=None, compare=False, repr=False)

    """
    Método estático para crear una categoría.

    @param nombre: Nombre de la categoría.
    @param categoria_padre_id: ID de la categoría padre.
    @return: Instancia de la clase Categoria.
    
    """
    @staticmethod
    def crear(nombre: str, categoria_padre_id: UUID | None = None) -> "Categoria":
        return Categoria(id=uuid4(), nombre=nombre, categoria_padre_id=categoria_padre_id, activo=True)

    """
    Método para actualizar una categoría.

    @param nombre: Nombre de la categoría.
    @param categoria_padre_id: ID de la categoría padre.
    @param cambiar_padre: Si es True, se cambia la categoría padre.
    @return: None
    
    """
    def actualizar(self, nombre: str | None = None, categoria_padre_id: UUID | None = None,
                   cambiar_padre: bool = False) -> None:
        if nombre is not None:
            self.nombre = nombre
        if cambiar_padre:
            self.categoria_padre_id = categoria_padre_id

    """
    Método para desactivar una categoría.
    @param self: Instancia de la clase Categoria.
    @return: None
    
    """
    def desactivar(self) -> None:
        self.activo = False
