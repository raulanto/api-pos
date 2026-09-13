"""`ResumenProveedorUseCase`: agrega defectos + devoluciones (fakes)."""
import uuid
from decimal import Decimal

from app.modules.proveedores.application.use_cases.reportes_proveedor import ResumenProveedorUseCase

PROVEEDOR = uuid.uuid4()


class _RecepcionRepo:
    async def resumen_defectos_por_proveedor(self, proveedor_id):
        return {
            "total_recibido": Decimal("100"),
            "total_defectuoso": Decimal("10"),
            "tiempo_real_promedio": Decimal("6.5"),
            "tiempo_prometido_promedio": Decimal("5"),
        }


class _DevolucionRepo:
    async def resumen_por_proveedor(self, proveedor_id):
        return {"pendientes": 1, "aceptadas": 2, "rechazadas": 1}


async def test_resumen_calcula_porcentaje_defectuoso():
    resumen = await ResumenProveedorUseCase(_RecepcionRepo(), _DevolucionRepo()).ejecutar(PROVEEDOR)
    assert resumen.pct_defectuoso == Decimal("10.00")
    assert resumen.devoluciones_aceptadas == 2
    assert resumen.tiempo_entrega_real_promedio_dias == Decimal("6.5")


class _RecepcionRepoSinRecibido:
    async def resumen_defectos_por_proveedor(self, proveedor_id):
        return {"total_recibido": Decimal("0"), "total_defectuoso": Decimal("0")}


async def test_resumen_sin_recepciones_no_divide_por_cero():
    resumen = await ResumenProveedorUseCase(_RecepcionRepoSinRecibido(), _DevolucionRepo()).ejecutar(
        PROVEEDOR,
    )
    assert resumen.pct_defectuoso == Decimal("0")
