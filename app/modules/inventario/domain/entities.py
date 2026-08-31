from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.inventario.domain.value_objects import TipoProducto, TipoMovimiento

@dataclass
class Categoria:
    id: UUID
    nombre: str
    categoria_padre_id: UUID | None
    activo: bool

    @staticmethod
    def crear(nombre: str, categoria_padre_id: UUID | None = None) -> "Categoria":
        return Categoria(id=uuid4(), nombre=nombre, categoria_padre_id=categoria_padre_id, activo=True)

@dataclass
class Producto:
    id: UUID
    sku: str
    codigo_barras: str | None
    nombre: str
    descripcion: str | None
    categoria_id: UUID
    unidad_medida: str
    precio_venta: Decimal
    costo: Decimal
    impuesto_tasa: Decimal
    tipo: TipoProducto
    permite_stock_negativo: bool
    activo: bool
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(
        sku: str, nombre: str, categoria_id: UUID, unidad_medida: str,
        precio_venta: Decimal, costo: Decimal, impuesto_tasa: Decimal,
        permite_stock_negativo: bool = False, codigo_barras: str | None = None,
        descripcion: str | None = None
    ) -> "Producto":
        return Producto(
            id=uuid4(),
            sku=sku,
            codigo_barras=codigo_barras,
            nombre=nombre,
            descripcion=descripcion,
            categoria_id=categoria_id,
            unidad_medida=unidad_medida,
            precio_venta=precio_venta,
            costo=costo,
            impuesto_tasa=impuesto_tasa,
            tipo=TipoProducto.SIMPLE,
            permite_stock_negativo=permite_stock_negativo,
            activo=True
        )

@dataclass
class Existencia:
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    cantidad: Decimal
    stock_minimo: Decimal
    stock_maximo: Decimal | None
    updated_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class MovimientoInventario:
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    tipo: TipoMovimiento
    cantidad: Decimal
    costo_unitario: Decimal | None
    referencia_tipo: str
    referencia_id: UUID | None
    usuario_id: UUID
    motivo: str | None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(
        producto_id: UUID, sucursal_id: UUID, tipo: TipoMovimiento, cantidad: Decimal,
        referencia_tipo: str, usuario_id: UUID, referencia_id: UUID | None = None,
        costo_unitario: Decimal | None = None, motivo: str | None = None
    ) -> "MovimientoInventario":
        if cantidad < 0:
            raise ValueError("La cantidad del movimiento debe ser siempre positiva.")
        
        return MovimientoInventario(
            id=uuid4(),
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            tipo=tipo,
            cantidad=cantidad,
            costo_unitario=costo_unitario,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            usuario_id=usuario_id,
            motivo=motivo
        )
