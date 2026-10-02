from dataclasses import dataclass
from uuid import UUID, uuid4


"""
Clase que representa una marca en el inventario.
Permite crear, actualizar y desactivar marcas.
"""
@dataclass
class Marca:
    id: UUID
    nombre: str
    activo: bool

    @staticmethod
    def crear(nombre: str) -> "Marca":
        return Marca(id=uuid4(), nombre=nombre, activo=True)

    def actualizar(self, nombre: str | None = None) -> None:
        if nombre is not None:
            self.nombre = nombre

    def desactivar(self) -> None:
        self.activo = False

    def activar(self) -> None:
        self.activo = True
