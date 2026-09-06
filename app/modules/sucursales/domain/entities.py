from dataclasses import dataclass
from datetime import datetime, time, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4


class TipoSucursal(str, Enum):
    BODEGA_CENTRAL = "bodega_central"
    TIENDA = "tienda"
    ALMACEN = "almacen"
    CEDIS = "cedis"
    OFICINA = "oficina"


"""
    Entidad que representa una SUCURSAL / ubicación física de la empresa.

    Deja de ser un catálogo pasivo: tiene jerarquía (una bodega central puede
    tener tiendas hijas), `tipo` con reglas distintas y `permite_ventas` que
    condiciona el módulo de ventas.

    @param imagen_fachada_key: key del objeto en el bucket (NO la URL). La URL
        pública se deriva prefirmada al leer (`imagen_fachada_url`, transitorio).
    @param sucursal_padre_id: auto-referencia; None = raíz del árbol.
    @param permite_ventas: si es False, no se pueden abrir turnos ni vender ahí.
"""
@dataclass
class Sucursal:
    id: UUID
    nombre: str
    direccion: str
    telefono: str
    activo: bool
    created_at: datetime
    tipo: TipoSucursal = TipoSucursal.TIENDA
    permite_ventas: bool = True
    codigo: str | None = None
    descripcion: str | None = None
    imagen_fachada_key: str | None = None
    colonia: str | None = None
    ciudad: str | None = None
    estado: str | None = None
    codigo_postal: str | None = None
    pais: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    email: str | None = None
    horario_apertura: time | None = None
    horario_cierre: time | None = None
    sucursal_padre_id: UUID | None = None
    updated_at: datetime | None = None
    # Derivado (no se persiste): URL GET prefirmada de la fachada. Lo rellena el mapper.
    imagen_fachada_url: str | None = None

    @staticmethod
    def crear(
        nombre: str, direccion: str, telefono: str,
        tipo: TipoSucursal = TipoSucursal.TIENDA,
        codigo: str | None = None, descripcion: str | None = None,
        colonia: str | None = None, ciudad: str | None = None,
        estado: str | None = None, codigo_postal: str | None = None,
        pais: str | None = "México", latitud: Decimal | None = None,
        longitud: Decimal | None = None, email: str | None = None,
        horario_apertura: time | None = None, horario_cierre: time | None = None,
        sucursal_padre_id: UUID | None = None, permite_ventas: bool = True,
    ) -> "Sucursal":
        return Sucursal(
            id=uuid4(),
            nombre=nombre,
            direccion=direccion,
            telefono=telefono,
            activo=True,
            created_at=datetime.now(timezone.utc),
            tipo=tipo,
            permite_ventas=permite_ventas,
            codigo=codigo.strip() if codigo else None,
            descripcion=descripcion,
            colonia=colonia,
            ciudad=ciudad,
            estado=estado,
            codigo_postal=codigo_postal,
            pais=pais,
            latitud=latitud,
            longitud=longitud,
            email=email,
            horario_apertura=horario_apertura,
            horario_cierre=horario_cierre,
            sucursal_padre_id=sucursal_padre_id,
        )

    def actualizar(
        self,
        nombre: str | None = None,
        direccion: str | None = None,
        telefono: str | None = None,
        tipo: TipoSucursal | None = None,
        permite_ventas: bool | None = None,
        codigo: str | None = None, cambiar_codigo: bool = False,
        descripcion: str | None = None, cambiar_descripcion: bool = False,
        colonia: str | None = None, cambiar_colonia: bool = False,
        ciudad: str | None = None, cambiar_ciudad: bool = False,
        estado: str | None = None, cambiar_estado: bool = False,
        codigo_postal: str | None = None, cambiar_codigo_postal: bool = False,
        pais: str | None = None, cambiar_pais: bool = False,
        latitud: Decimal | None = None, longitud: Decimal | None = None,
        cambiar_geo: bool = False,
        email: str | None = None, cambiar_email: bool = False,
        horario_apertura: time | None = None, horario_cierre: time | None = None,
        cambiar_horario: bool = False,
        sucursal_padre_id: UUID | None = None, cambiar_padre: bool = False,
    ) -> None:
        if nombre is not None:
            self.nombre = nombre
        if direccion is not None:
            self.direccion = direccion
        if telefono is not None:
            self.telefono = telefono
        if tipo is not None:
            self.tipo = tipo
        if permite_ventas is not None:
            self.permite_ventas = permite_ventas
        if cambiar_codigo:
            self.codigo = codigo.strip() if codigo else None
        if cambiar_descripcion:
            self.descripcion = descripcion
        if cambiar_colonia:
            self.colonia = colonia
        if cambiar_ciudad:
            self.ciudad = ciudad
        if cambiar_estado:
            self.estado = estado
        if cambiar_codigo_postal:
            self.codigo_postal = codigo_postal
        if cambiar_pais:
            self.pais = pais
        if cambiar_geo:
            self.latitud = latitud
            self.longitud = longitud
        if cambiar_email:
            self.email = email
        if cambiar_horario:
            self.horario_apertura = horario_apertura
            self.horario_cierre = horario_cierre
        if cambiar_padre:
            self.sucursal_padre_id = sucursal_padre_id

    def desactivar(self) -> None:
        self.activo = False

    def activar(self) -> None:
        self.activo = True
