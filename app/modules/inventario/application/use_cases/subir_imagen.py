"""Caso de uso: subir el binario de una imagen (multipart) y guardarlo en S3.

Espeja `AgregarImagenUseCase` (imágenes por URL externa) pero recibe los bytes:
1. Valida el dueño (producto XOR presentación) reusando `_validar_dueno`.
2. Valida `content_type` (allowlist) y tamaño.
3. Sube el objeto a S3 bajo `originales/...` (esto dispara la Lambda de miniaturas).
4. Persiste la fila `producto_imagen` con la `object_key`.

Si el paso 4 (o el commit del request) falla, el objeto recién subido queda
huérfano: se compensa borrándolo en el `except`.
"""
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.modules.inventario.domain.entities import ProductoImagen
from app.modules.inventario.domain.exceptions import ImagenInvalida
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.unidad_repository import (
    ProductoUnidadRepository,
)
from app.modules.inventario.application.ports.imagen_repository import ImagenRepository
from app.modules.inventario.application.ports.almacen_imagenes import (
    AlmacenImagenes, EXTENSIONES_PERMITIDAS,
)
from app.modules.inventario.application.use_cases.gestionar_imagenes import _validar_dueno


@dataclass
class SubirImagenInput:
    contenido: bytes
    content_type: str
    producto_id: UUID | None = None
    producto_unidad_id: UUID | None = None
    alt_texto: str | None = None
    orden: int = 0
    es_principal: bool = False


class SubirImagenUseCase:
    def __init__(
        self,
        imagen_repo: ImagenRepository,
        producto_repo: ProductoRepository,
        unidad_repo: ProductoUnidadRepository,
        almacen: AlmacenImagenes,
    ):
        self._repo = imagen_repo
        self._producto_repo = producto_repo
        self._unidad_repo = unidad_repo
        self._almacen = almacen

    async def ejecutar(self, data: SubirImagenInput) -> ProductoImagen:
        await _validar_dueno(
            self._producto_repo, self._unidad_repo,
            data.producto_id, data.producto_unidad_id,
        )

        content_type = (data.content_type or "").split(";")[0].strip().lower()
        if content_type not in EXTENSIONES_PERMITIDAS:
            raise ImagenInvalida(
                f"Tipo de archivo no permitido: '{content_type}'. "
                f"Se aceptan: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}."
            )
        if not data.contenido:
            raise ImagenInvalida("El archivo está vacío.")
        if len(data.contenido) > settings.imagen_max_bytes:
            limite_mb = settings.imagen_max_bytes / (1024 * 1024)
            raise ImagenInvalida(f"El archivo supera el límite de {limite_mb:.0f} MiB.")

        if data.producto_id is not None:
            dueno, dueno_id = "producto", data.producto_id
        else:
            dueno, dueno_id = "unidad", data.producto_unidad_id
        key = self._almacen.nueva_key(
            dueno=dueno, dueno_id=dueno_id, content_type=content_type
        )

        await self._almacen.subir(data.contenido, content_type, key)
        try:
            imagen = ProductoImagen.crear_desde_s3(
                object_key=key,
                content_type=content_type,
                producto_id=data.producto_id,
                producto_unidad_id=data.producto_unidad_id,
                alt_texto=data.alt_texto,
                orden=data.orden,
                es_principal=data.es_principal,
            )
            if data.es_principal:
                await self._repo.desmarcar_principal(
                    data.producto_id, data.producto_unidad_id
                )
            await self._repo.crear(imagen)
        except Exception:
            await self._almacen.eliminar(key)   # compensación: no dejar objeto huérfano
            raise

        # Deja la entidad igual que una leída por el mapper: `url` y
        # `thumbnail_url` prefirmadas, para que el 201 ya sirva para mostrar.
        imagen.url = self._almacen.url_publica(key)
        imagen.thumbnail_url = self._almacen.url_publica(
            AlmacenImagenes.key_miniatura(key)
        )
        return imagen
