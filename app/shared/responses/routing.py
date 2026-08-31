from fastapi.routing import APIRoute


class EnvelopeRoute(APIRoute):
    """Marcador de routers que responden con el sobre `ApiResponse`.

    El recorte de `meta`/`links` cuando no aplican lo hace el propio
    `ApiResponse` (model_serializer), no la ruta, así que esta clase hoy es un
    passthrough; se mantiene como punto de extensión común de los routers
    normalizados.
    """

    pass
