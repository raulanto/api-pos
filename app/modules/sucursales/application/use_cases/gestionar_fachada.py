"""Casos de uso de la imagen de fachada de una sucursal (subir / eliminar).

El binario vive en S3; en BD solo se guarda `imagen_fachada_key`. La URL pública
se deriva prefirmada al leer (en `to_domain_sucursal`).
"""
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.modules.sucursales.domain.entities import Sucursal
from app.modules.sucursales.domain.exceptions import SucursalNoEncontrada
from app.modules.sucursales.application.ports.sucursal_repository import SucursalRepository
from app.modules.sucursales.infrastructure.storage import fachada_storage


@dataclass
class SubirFachadaInput:
    sucursal_id: UUID
    contenido: bytes
    content_type: str


class SubirFachadaUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, data: SubirFachadaInput) -> Sucursal:
        sucursal = await self._repo.obtener_por_id(data.sucursal_id)
        if sucursal is None:
            raise SucursalNoEncontrada(f"No existe sucursal con id {data.sucursal_id}")

        content_type = (data.content_type or "").split(";")[0].strip().lower()
        if not fachada_storage.content_type_valido(content_type):
            raise ValueError(
                f"Tipo de archivo no permitido: '{content_type}'. Se aceptan: "
                f"{', '.join(sorted(fachada_storage.EXTENSIONES_PERMITIDAS))}."
            )
        if not data.contenido:
            raise ValueError("El archivo está vacío.")
        if len(data.contenido) > settings.imagen_max_bytes:
            limite_mb = settings.imagen_max_bytes / (1024 * 1024)
            raise ValueError(f"El archivo supera el límite de {limite_mb:.0f} MiB.")

        key_anterior = sucursal.imagen_fachada_key
        key = fachada_storage.nueva_key(data.sucursal_id, content_type)
        await fachada_storage.subir(key, data.contenido, content_type)
        try:
            sucursal.imagen_fachada_key = key
            await self._repo.actualizar(sucursal)
        except Exception:
            await fachada_storage.eliminar(key)   # compensación
            raise

        if key_anterior and key_anterior != key:
            await fachada_storage.eliminar(key_anterior)
        sucursal.imagen_fachada_url = fachada_storage.url_publica(key)
        return sucursal


class EliminarFachadaUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, sucursal_id: UUID) -> Sucursal:
        sucursal = await self._repo.obtener_por_id(sucursal_id)
        if sucursal is None:
            raise SucursalNoEncontrada(f"No existe sucursal con id {sucursal_id}")
        key = sucursal.imagen_fachada_key
        if key:
            sucursal.imagen_fachada_key = None
            sucursal.imagen_fachada_url = None
            await self._repo.actualizar(sucursal)
            await fachada_storage.eliminar(key)
        return sucursal
