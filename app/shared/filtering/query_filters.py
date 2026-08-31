"""Serialización de los filtros activos para `meta.filters`.

Los módulos ya definen sus `Filtro*` como dataclasses con campos tipados
(whitelist implícita). Acá solo se traduce a un dict JSON-eable con las claves
que realmente se aplicaron, para reflejarlas en la respuesta.
"""
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def active_filters(filtro: Any) -> dict[str, Any]:
    """Devuelve {campo: valor} para los campos con valor significativo.

    Se omiten los `None` y los `bool` en False (valor por defecto = filtro
    inactivo).
    """
    if filtro is None or not is_dataclass(filtro):
        return {}
    out: dict[str, Any] = {}
    for f in fields(filtro):
        v = getattr(filtro, f.name)
        if v is None:
            continue
        if isinstance(v, bool) and v is False:
            continue
        out[f.name] = _jsonable(v)
    return out
