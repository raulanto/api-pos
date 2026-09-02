from dataclasses import dataclass


@dataclass
class FiltroSucursales:
    activo: bool | None = None
    busqueda: str | None = None  # coincide contra nombre / dirección / teléfono
