from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.modules.inventario.domain.value_objects import TipoMagnitud


"""
    Entidad del catálogo de unidades de medida.

    Normaliza el texto libre que antes vivía en `producto.unidad_medida` y
    `producto_unidad.unidad_medida`: "pza" / "pieza" / "pzas" pasan a ser una
    sola fila. `decimales` fija cuántos decimales admite una cantidad expresada
    en esta unidad (0 para piezas, 3 para kg/l, etc.); lo usan el redondeo de
    stock y las validaciones de venta fraccionada.

    @param id: ID de la unidad.
    @param codigo: Clave corta única ("kg", "l", "pza", "reja").
    @param nombre: Nombre visible ("Kilogramo").
    @param tipo_magnitud: Magnitud física que mide (para agrupar/convertir).
    @param decimales: Decimales admitidos en una cantidad de esta unidad (>= 0).
    @param activo: Baja lógica.
    @param created_at: Fecha de alta.
"""
@dataclass
class UnidadMedida:
    id: UUID
    codigo: str
    nombre: str
    tipo_magnitud: TipoMagnitud
    decimales: int
    activo: bool = True
    created_at: datetime = None  # type: ignore[assignment]

    @staticmethod
    def crear(
        codigo: str, nombre: str, tipo_magnitud: TipoMagnitud, decimales: int = 0
    ) -> "UnidadMedida":
        if decimales < 0 or decimales > 6:
            raise ValueError("`decimales` debe estar entre 0 y 6.")
        return UnidadMedida(
            id=uuid4(),
            codigo=codigo.strip().lower(),
            nombre=nombre.strip(),
            tipo_magnitud=tipo_magnitud,
            decimales=decimales,
            activo=True,
            created_at=datetime.now(timezone.utc),
        )

    def actualizar(
        self,
        nombre: str | None = None,
        tipo_magnitud: TipoMagnitud | None = None,
        decimales: int | None = None,
    ) -> None:
        if nombre is not None:
            self.nombre = nombre.strip()
        if tipo_magnitud is not None:
            self.tipo_magnitud = tipo_magnitud
        if decimales is not None:
            if decimales < 0 or decimales > 6:
                raise ValueError("`decimales` debe estar entre 0 y 6.")
            self.decimales = decimales

    def desactivar(self) -> None:
        self.activo = False

    def activar(self) -> None:
        self.activo = True
