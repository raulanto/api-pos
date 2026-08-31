from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

@dataclass
class Permiso:
    id: UUID
    codigo: str
    descripcion: str

@dataclass
class Rol:
    id: UUID
    nombre: str
    descripcion: str
    permisos: list[Permiso] = field(default_factory=list)

@dataclass
class Sucursal:
    id: UUID
    nombre: str
    direccion: str
    telefono: str
    activo: bool
    created_at: datetime

@dataclass
class Usuario:
    id: UUID
    sucursal_id: UUID | None
    rol_id: UUID
    nombre: str
    email: str
    password_hash: str
    activo: bool = True
    last_login_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(sucursal_id: UUID | None, rol_id: UUID, nombre: str, email: str, password_hash: str) -> "Usuario":
        return Usuario(
            id=uuid4(),
            sucursal_id=sucursal_id,
            rol_id=rol_id,
            nombre=nombre,
            email=email,
            password_hash=password_hash,
        )
