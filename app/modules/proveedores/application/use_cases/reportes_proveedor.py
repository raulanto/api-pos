from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.proveedores.application.ports.recepcion_proveedor_repository import (
    RecepcionProveedorRepository,
)
from app.modules.proveedores.application.ports.devolucion_proveedor_repository import (
    DevolucionProveedorRepository,
)


@dataclass
class ResumenProveedor:
    proveedor_id: UUID
    total_unidades_recibidas: Decimal
    total_unidades_defectuosas: Decimal
    pct_defectuoso: Decimal
    tiempo_entrega_prometido_dias: Decimal | None
    tiempo_entrega_real_promedio_dias: Decimal | None
    devoluciones_pendientes: int
    devoluciones_aceptadas: int
    devoluciones_rechazadas: int


class ResumenProveedorUseCase:
    """Reporte acotado de Fase 5: % de defectuosos, tiempo de entrega real vs
    prometido, conteo de devoluciones por resultado. Vive en `proveedores`
    (no en el módulo `reportes`) porque es específico de este dominio."""

    def __init__(
        self, recepcion_repo: RecepcionProveedorRepository,
        devolucion_repo: DevolucionProveedorRepository,
    ):
        self._recepcion_repo = recepcion_repo
        self._devolucion_repo = devolucion_repo

    async def ejecutar(self, proveedor_id: UUID) -> ResumenProveedor:
        defectos = await self._recepcion_repo.resumen_defectos_por_proveedor(proveedor_id)
        devoluciones = await self._devolucion_repo.resumen_por_proveedor(proveedor_id)

        total = Decimal(defectos.get("total_recibido") or 0)
        defectuoso = Decimal(defectos.get("total_defectuoso") or 0)
        pct = (defectuoso / total * 100) if total > 0 else Decimal("0")

        return ResumenProveedor(
            proveedor_id=proveedor_id,
            total_unidades_recibidas=total,
            total_unidades_defectuosas=defectuoso,
            pct_defectuoso=pct.quantize(Decimal("0.01")),
            tiempo_entrega_prometido_dias=defectos.get("tiempo_prometido_promedio"),
            tiempo_entrega_real_promedio_dias=defectos.get("tiempo_real_promedio"),
            devoluciones_pendientes=devoluciones.get("pendientes", 0),
            devoluciones_aceptadas=devoluciones.get("aceptadas", 0),
            devoluciones_rechazadas=devoluciones.get("rechazadas", 0),
        )
