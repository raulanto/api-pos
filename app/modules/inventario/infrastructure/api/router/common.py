from uuid import UUID

from fastapi import HTTPException, status

from app.core.dependencies import UsuarioAutenticado, sucursal_scope
from app.modules.inventario.domain import exceptions as exc
from app.modules.inventario.infrastructure.persistence.repositories import (
    SqlAlchemyCategoriaRepository,
    SqlAlchemyProductoRepository,
    SqlAlchemyProductoComponenteRepository,
    SqlAlchemyProductoUnidadRepository,
    SqlAlchemyExistenciaRepository,
    SqlAlchemyMovimientoRepository,
)


"""
    Mapeo de excepciones de dominio -> HTTP

    @param error: Excepción a traducir.
    @return: Instancia de la clase HTTPException.
"""
_NOT_FOUND = (
    exc.ProductoNoEncontrado, exc.CategoriaNoEncontrada, exc.ExistenciaNoEncontrada,
    exc.MovimientoNoEncontrado, exc.ComponenteNoEncontrado, exc.UnidadNoEncontrada,
)


"""
    Conflictos   de recursos.

    @param error: Excepción a traducir.
    @return: Instancia de la clase HTTPException.
"""
_CONFLICT = (
    exc.CategoriaConProductosActivos, exc.ProductoConStockActivo,
    exc.ComponenteDuplicado, exc.ProductoEsComponenteDeKit,
    exc.UnidadDuplicada, exc.CodigoBarrasUnidadDuplicado,
)


"""
    Solicitudes incorrectas.

    @param error: Excepción a traducir.
    @return: Instancia de la clase HTTPException.
"""
_BAD_REQUEST = (
    exc.SkuDuplicado, exc.CodigoBarrasDuplicado, exc.StockInsuficiente,
    exc.AjusteSinCantidadFinal, exc.TransferenciaInvalida, exc.JerarquiaCategoriaInvalida,
    exc.ProductoInactivo, exc.KitInvalido, exc.ComponenteInvalido, exc.UnidadInvalida,
    ValueError,
)



"""
    Traduce excepciones de dominio a respuestas HTTP.

    @param error: Excepción a traducir.
    @return: Instancia de la clase HTTPException.
"""
def traducir(error: Exception) -> HTTPException:
    if isinstance(error, _NOT_FOUND):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, _CONFLICT):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, _BAD_REQUEST):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


"""
    Traduce excepciones de dominio a respuestas HTTP.

    @param error: Excepción a traducir.
    @return: Instancia de la clase HTTPException.
"""
def traducir_create(error: Exception) -> HTTPException:
    if isinstance(error, exc.CategoriaNoEncontrada):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    return traducir(error)




"""
    Fábrica de repositorio de categorías.

    @param db: Sesión de la base de datos.
    @return: Instancia de la clase SqlAlchemyCategoriaRepository.
"""
def cat_repo(db):
    return SqlAlchemyCategoriaRepository(db)


"""
    Fábrica de repositorio de productos.

    @param db: Sesión de la base de datos.
    @return: Instancia de la clase SqlAlchemyProductoRepository.
"""
def prod_repo(db):
    return SqlAlchemyProductoRepository(db)


"""
    Fábrica de repositorio de componentes de kit.

    @param db: Sesión de la base de datos.
    @return: Instancia de la clase SqlAlchemyProductoComponenteRepository.
"""
def comp_repo(db):
    return SqlAlchemyProductoComponenteRepository(db)


"""
    Fábrica de repositorio de presentaciones de venta (producto_unidad).

    @param db: Sesión de la base de datos.
    @return: Instancia de la clase SqlAlchemyProductoUnidadRepository.
"""
def unidad_repo(db):
    return SqlAlchemyProductoUnidadRepository(db)


"""
    Fábrica de repositorio de existencias.

    @param db: Sesión de la base de datos.
    @return: Instancia de la clase SqlAlchemyExistenciaRepository.
"""
def exist_repo(db):
    return SqlAlchemyExistenciaRepository(db)


"""
    Fábrica de repositorio de movimientos.

    @param db: Sesión de la base de datos.
    @return: Instancia de la clase SqlAlchemyMovimientoRepository.
"""
def mov_repo(db):
    return SqlAlchemyMovimientoRepository(db)


"""
    Devuelve la sucursal efectiva.

    @param actual: Usuario autenticado.
    @param pedida: ID de la sucursal.
    @return: Instancia de la clase UUID.
"""
def sucursal_efectiva(actual: UsuarioAutenticado, pedida: UUID | None) -> UUID | None:
    """Sección 10/11: los roles no globales quedan atados a su sucursal.

    - rol global (admin/gerente): respeta el filtro pedido, o None => todas.
    - rol de sucursal: siempre su propia sucursal; si pide otra distinta => 403.
    """
    alcance = sucursal_scope(actual)  # None => global
    if alcance is None:
        return pedida
    if pedida is not None and pedida != alcance:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Fuera del alcance de su sucursal")
    return alcance


"""
    Versión multi-valor de `sucursal_efectiva` para el filtro `?sucursal_id=` que
    admite varias sucursales.

    @param actual: Usuario autenticado.
    @param pedidas: Lista de IDs de sucursal pedidos (o None => sin filtro).
    @return: Lista de sucursales a aplicar, o None para "todas".
"""
def sucursales_efectivas(
    actual: UsuarioAutenticado, pedidas: list[UUID] | None
) -> list[UUID] | None:
    """Mismo criterio que `sucursal_efectiva`:

    - rol global (admin/gerente): respeta las sucursales pedidas, o None => todas.
    - rol de sucursal: siempre acotado a la suya; si pide alguna distinta => 403.
    """
    alcance = sucursal_scope(actual)  # None => global
    pedidas = pedidas or None
    if alcance is None:
        return pedidas
    if pedidas is not None and any(s != alcance for s in pedidas):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Fuera del alcance de su sucursal")
    return [alcance]
