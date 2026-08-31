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

    def actualizar(self, nombre: str | None = None, categoria_padre_id: UUID | None = None,
                   cambiar_padre: bool = False) -> None:
        if nombre is not None:
            self.nombre = nombre
        if cambiar_padre:
            self.categoria_padre_id = categoria_padre_id

    def desactivar(self) -> None:
        self.activo = False

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

    def actualizar(
        self,
        nombre: str | None = None,
        descripcion: str | None = None,
        categoria_id: UUID | None = None,
        unidad_medida: str | None = None,
        precio_venta: Decimal | None = None,
        costo: Decimal | None = None,
        impuesto_tasa: Decimal | None = None,
        permite_stock_negativo: bool | None = None,
        codigo_barras: str | None = None,
        cambiar_codigo_barras: bool = False,
    ) -> None:
        if nombre is not None:
            self.nombre = nombre
        if descripcion is not None:
            self.descripcion = descripcion
        if categoria_id is not None:
            self.categoria_id = categoria_id
        if unidad_medida is not None:
            self.unidad_medida = unidad_medida
        if precio_venta is not None:
            self.precio_venta = precio_venta
        if costo is not None:
            self.costo = costo
        if impuesto_tasa is not None:
            self.impuesto_tasa = impuesto_tasa
        if permite_stock_negativo is not None:
            self.permite_stock_negativo = permite_stock_negativo
        if cambiar_codigo_barras:
            self.codigo_barras = codigo_barras

    def desactivar(self) -> None:
        self.activo = False

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
