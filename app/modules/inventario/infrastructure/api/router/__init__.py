from fastapi import APIRouter

from .categorias import router as categorias_router
from .productos import router as productos_router
from .existencias import router as existencias_router
from .movimientos import router as movimientos_router

router = APIRouter()

router.include_router(categorias_router)
router.include_router(productos_router)
router.include_router(existencias_router)
router.include_router(movimientos_router)
