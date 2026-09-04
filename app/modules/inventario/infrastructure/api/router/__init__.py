from fastapi import APIRouter

from .categorias import router as categorias_router
from .productos import router as productos_router
from .componentes import router as componentes_router
from .unidades import router as unidades_router
from .existencias import router as existencias_router
from .movimientos import router as movimientos_router

router = APIRouter()

router.include_router(categorias_router)
# `unidades` antes que `productos`: su ruta literal `/productos/resolver-codigo`
# tiene que ganarle al comodín `/productos/{producto_id}`.
router.include_router(unidades_router)
router.include_router(productos_router)
router.include_router(componentes_router)
router.include_router(existencias_router)
router.include_router(movimientos_router)
