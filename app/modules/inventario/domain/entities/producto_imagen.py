from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


"""
    Entidad que representa una imagen del catálogo.

    El dueño es EXACTAMENTE uno de los dos: un producto (simple o kit) o una
    presentación de venta (`producto_unidad`, p. ej. la unidad suelta de una
    reja fraccionable). Es una galería: puede haber varias por dueño, con
    `orden` para el carrusel y `es_principal` para la miniatura de catálogo.

    @param id: ID de la imagen.
    @param producto_id: Dueño si es una imagen de producto (XOR con el otro).
    @param producto_unidad_id: Dueño si es una imagen de una presentación.
    @param url: URL de la imagen (servida desde donde el cliente la suba).
    @param alt_texto: Texto alternativo / descripción.
    @param orden: Posición en la galería (0 = primera).
    @param es_principal: Miniatura/portada del dueño.
    @param created_at: Fecha de alta.
"""
@dataclass
class ProductoImagen:
    id: UUID
    producto_id: UUID | None
    producto_unidad_id: UUID | None
    url: str
    alt_texto: str | None
    orden: int
    es_principal: bool
    created_at: datetime = None  # type: ignore[assignment]

    @staticmethod
    def crear(
        url: str, producto_id: UUID | None = None, producto_unidad_id: UUID | None = None,
        alt_texto: str | None = None, orden: int = 0, es_principal: bool = False,
    ) -> "ProductoImagen":
        return ProductoImagen(
            id=uuid4(),
            producto_id=producto_id,
            producto_unidad_id=producto_unidad_id,
            url=url,
            alt_texto=alt_texto,
            orden=orden,
            es_principal=es_principal,
            created_at=datetime.now(timezone.utc),
        )

    def actualizar(
        self,
        url: str | None = None,
        alt_texto: str | None = None,
        cambiar_alt_texto: bool = False,
        orden: int | None = None,
        es_principal: bool | None = None,
    ) -> None:
        if url is not None:
            self.url = url
        if cambiar_alt_texto:
            self.alt_texto = alt_texto
        elif alt_texto is not None:
            self.alt_texto = alt_texto
        if orden is not None:
            self.orden = orden
        if es_principal is not None:
            self.es_principal = es_principal
