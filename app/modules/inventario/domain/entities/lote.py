from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4


"""
    Entidad que representa un LOTE de un producto.

    Un lote es un ingreso identificable de mercadería (código del proveedor /
    fabricante) con su propia fecha de caducidad y su propio costo. El stock del
    lote por sucursal vive en `ExistenciaLote`; un mismo lote puede tener
    existencia en varias sucursales.

    @param id: ID del lote.
    @param producto_id: Producto al que pertenece.
    @param codigo_lote: Código del lote (del proveedor/fabricante). Único por
        producto entre lotes activos.
    @param fecha_caducidad: Fecha de vencimiento (None = no vence / sin dato). En
        el orden FEFO los None van al final.
    @param costo: Costo unitario (en unidad base) de la mercadería de este lote.
    @param proveedor: Nombre del proveedor (texto libre, opcional).
    @param activo: Baja lógica; los movimientos históricos siguen apuntando acá.
    @param created_at: Fecha de alta.
"""
@dataclass
class Lote:
    id: UUID
    producto_id: UUID
    codigo_lote: str
    fecha_caducidad: date | None
    costo: Decimal
    proveedor: str | None = None
    activo: bool = True
    created_at: datetime = None  # type: ignore[assignment]

    @staticmethod
    def crear(
        producto_id: UUID, codigo_lote: str, costo: Decimal,
        fecha_caducidad: date | None = None, proveedor: str | None = None,
    ) -> "Lote":
        if costo is None or costo < 0:
            raise ValueError("El costo del lote no puede ser negativo.")
        return Lote(
            id=uuid4(),
            producto_id=producto_id,
            codigo_lote=codigo_lote.strip(),
            fecha_caducidad=fecha_caducidad,
            costo=costo,
            proveedor=proveedor.strip() if proveedor else None,
            activo=True,
            created_at=datetime.now(timezone.utc),
        )

    def actualizar(
        self,
        codigo_lote: str | None = None,
        fecha_caducidad: date | None = None,
        cambiar_fecha_caducidad: bool = False,
        costo: Decimal | None = None,
        proveedor: str | None = None,
        cambiar_proveedor: bool = False,
    ) -> None:
        if codigo_lote is not None:
            self.codigo_lote = codigo_lote.strip()
        if cambiar_fecha_caducidad:
            self.fecha_caducidad = fecha_caducidad
        elif fecha_caducidad is not None:
            self.fecha_caducidad = fecha_caducidad
        if costo is not None:
            if costo < 0:
                raise ValueError("El costo del lote no puede ser negativo.")
            self.costo = costo
        if cambiar_proveedor:
            self.proveedor = proveedor.strip() if proveedor else None
        elif proveedor is not None:
            self.proveedor = proveedor.strip()

    def desactivar(self) -> None:
        self.activo = False

    def activar(self) -> None:
        self.activo = True
