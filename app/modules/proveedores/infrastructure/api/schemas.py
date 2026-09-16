from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.proveedores.domain.value_objects import (
    TipoPersona, CondicionesPago, EstadoPedidoProveedor, EstadoRecepcion,
    MotivoDefecto, AccionDefecto, EstadoDevolucionProveedor, ResultadoDevolucion,
    TipoResolucionDevolucion,
)

_ORM = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Proveedor
# --------------------------------------------------------------------------- #
class ProveedorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str = Field(min_length=1, max_length=30)
    razon_social: str = Field(min_length=1, max_length=200)
    tipo_persona: TipoPersona
    condiciones_pago: CondicionesPago
    dias_credito: Optional[int] = Field(default=None, gt=0)
    nombre_comercial: Optional[str] = Field(default=None, max_length=200)
    rfc: Optional[str] = Field(default=None, max_length=20)
    moneda: str = Field(default="MXN", max_length=3)
    contacto_principal: Optional[str] = Field(default=None, max_length=150)
    telefono: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=150)
    direccion_calle: Optional[str] = None
    direccion_numero: Optional[str] = None
    direccion_colonia: Optional[str] = None
    direccion_ciudad: Optional[str] = None
    direccion_estado: Optional[str] = None
    direccion_codigo_postal: Optional[str] = None
    notas: Optional[str] = None


class ProveedorUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    razon_social: Optional[str] = None
    tipo_persona: Optional[TipoPersona] = None
    condiciones_pago: Optional[CondicionesPago] = None
    dias_credito: Optional[int] = Field(default=None, gt=0)
    cambiar_dias_credito: bool = False
    moneda: Optional[str] = None
    nombre_comercial: Optional[str] = None
    cambiar_nombre_comercial: bool = False
    rfc: Optional[str] = None
    cambiar_rfc: bool = False
    contacto_principal: Optional[str] = None
    cambiar_contacto_principal: bool = False
    telefono: Optional[str] = None
    cambiar_telefono: bool = False
    email: Optional[str] = None
    cambiar_email: bool = False
    notas: Optional[str] = None
    cambiar_notas: bool = False
    direccion_calle: Optional[str] = None
    direccion_numero: Optional[str] = None
    direccion_colonia: Optional[str] = None
    direccion_ciudad: Optional[str] = None
    direccion_estado: Optional[str] = None
    direccion_codigo_postal: Optional[str] = None


class ProveedorResponse(BaseModel):
    model_config = _ORM
    id: UUID
    codigo: str
    razon_social: str
    nombre_comercial: Optional[str] = None
    rfc: Optional[str] = None
    tipo_persona: TipoPersona
    condiciones_pago: CondicionesPago
    dias_credito: Optional[int] = None
    moneda: str
    contacto_principal: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion_calle: Optional[str] = None
    direccion_numero: Optional[str] = None
    direccion_colonia: Optional[str] = None
    direccion_ciudad: Optional[str] = None
    direccion_estado: Optional[str] = None
    direccion_codigo_postal: Optional[str] = None
    activo: bool
    notas: Optional[str] = None
    created_at: datetime


# --------------------------------------------------------------------------- #
# ProductoProveedor
# --------------------------------------------------------------------------- #
class ProductoProveedorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proveedor_id: UUID
    precio_compra: Decimal = Field(ge=0)
    tiempo_entrega_dias: int = Field(ge=0)
    stock_minimo: Decimal = Field(ge=0)
    cantidad_reorden: Decimal = Field(gt=0)
    codigo_proveedor: Optional[str] = Field(default=None, max_length=60)
    stock_maximo: Optional[Decimal] = Field(default=None, ge=0)
    es_proveedor_principal: bool = False


class ProductoProveedorResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    proveedor_id: UUID
    codigo_proveedor: Optional[str] = None
    precio_compra: Decimal
    tiempo_entrega_dias: int
    stock_minimo: Decimal
    stock_maximo: Optional[Decimal] = None
    cantidad_reorden: Decimal
    es_proveedor_principal: bool
    activo: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Pedido a proveedor
# --------------------------------------------------------------------------- #
class LineaPedidoProveedorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producto_id: UUID
    cantidad_solicitada: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)


class PedidoProveedorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proveedor_id: UUID
    lineas: List[LineaPedidoProveedorRequest] = Field(min_length=1)
    fecha_estimada_entrega: Optional[date] = None
    notas: Optional[str] = None


class PedidoProveedorLineaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    cantidad_solicitada: Decimal
    cantidad_recibida: Decimal
    precio_unitario: Decimal
    subtotal: Decimal
    pendiente: Decimal


class PedidoProveedorResponse(BaseModel):
    model_config = _ORM
    id: UUID
    folio: str
    proveedor_id: UUID
    sucursal_id: UUID
    estado: EstadoPedidoProveedor
    generado_automaticamente: bool
    generado_por: Optional[UUID] = None
    confirmado_por: Optional[UUID] = None
    fecha_pedido: datetime
    fecha_estimada_entrega: Optional[date] = None
    subtotal: Decimal
    notas: Optional[str] = None
    created_at: datetime
    lineas: List[PedidoProveedorLineaResponse] = []


# --------------------------------------------------------------------------- #
# Recepción
# --------------------------------------------------------------------------- #
class LineaRecepcionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producto_id: UUID
    cantidad_recibida_buena: Decimal = Field(ge=0)
    cantidad_defectuosa: Decimal = Field(default=Decimal("0"), ge=0)
    cantidad_esperada: Optional[Decimal] = Field(default=None, ge=0)
    motivo_defecto: Optional[MotivoDefecto] = None
    accion_defecto: Optional[AccionDefecto] = None
    fotos_evidencia_keys: List[str] = []
    notas: Optional[str] = None


class RecepcionProveedorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proveedor_id: UUID
    lineas: List[LineaRecepcionRequest] = Field(min_length=1)
    pedido_id: Optional[UUID] = None
    numero_factura: Optional[str] = Field(default=None, max_length=60)
    numero_remision: Optional[str] = Field(default=None, max_length=60)
    transportista: Optional[str] = Field(default=None, max_length=120)
    notas: Optional[str] = None


class RecepcionProveedorLineaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    cantidad_esperada: Optional[Decimal] = None
    cantidad_recibida_buena: Decimal
    cantidad_defectuosa: Decimal
    motivo_defecto: Optional[MotivoDefecto] = None
    accion_defecto: Optional[AccionDefecto] = None
    fotos_evidencia_keys: List[str] = []
    notas: Optional[str] = None


class RecepcionProveedorResponse(BaseModel):
    model_config = _ORM
    id: UUID
    folio: str
    pedido_id: Optional[UUID] = None
    proveedor_id: UUID
    sucursal_id: UUID
    numero_factura: Optional[str] = None
    numero_remision: Optional[str] = None
    transportista: Optional[str] = None
    recibido_por: UUID
    fecha_recepcion: datetime
    estado: EstadoRecepcion
    notas: Optional[str] = None
    created_at: datetime
    lineas: List[RecepcionProveedorLineaResponse] = []


# --------------------------------------------------------------------------- #
# Devolución a proveedor
# --------------------------------------------------------------------------- #
class LineaDevolucionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recepcion_detalle_id: UUID
    cantidad: Decimal = Field(gt=0)


class DevolucionProveedorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proveedor_id: UUID
    recepcion_id: UUID
    lineas: List[LineaDevolucionRequest] = Field(min_length=1)
    notas: Optional[str] = None


class CerrarDevolucionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resultado: ResultadoDevolucion
    tipo_resolucion: Optional[TipoResolucionDevolucion] = None


class DevolucionProveedorLineaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    recepcion_detalle_id: UUID
    producto_id: UUID
    cantidad: Decimal


class DevolucionProveedorResponse(BaseModel):
    model_config = _ORM
    id: UUID
    folio: str
    proveedor_id: UUID
    recepcion_id: UUID
    creado_por: UUID
    estado: EstadoDevolucionProveedor
    resultado: Optional[ResultadoDevolucion] = None
    tipo_resolucion: Optional[TipoResolucionDevolucion] = None
    fecha_envio: Optional[datetime] = None
    fecha_cierre: Optional[datetime] = None
    notas: Optional[str] = None
    created_at: datetime
    lineas: List[DevolucionProveedorLineaResponse] = []


# --------------------------------------------------------------------------- #
# Reorden / reportes
# --------------------------------------------------------------------------- #
class ReordenGeneradoResponse(BaseModel):
    pedido: PedidoProveedorResponse
    fue_creado: bool


class ResumenProveedorResponse(BaseModel):
    proveedor_id: UUID
    total_unidades_recibidas: Decimal
    total_unidades_defectuosas: Decimal
    pct_defectuoso: Decimal
    tiempo_entrega_prometido_dias: Optional[Decimal] = None
    tiempo_entrega_real_promedio_dias: Optional[Decimal] = None
    devoluciones_pendientes: int
    devoluciones_aceptadas: int
    devoluciones_rechazadas: int
