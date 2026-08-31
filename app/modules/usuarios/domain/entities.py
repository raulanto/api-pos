from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

ROL_ADMIN = "admin"


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
    codigo: str | None = None
    permisos: list[Permiso] = field(default_factory=list)

    @property
    def es_admin(self) -> bool:
        return self.codigo == ROL_ADMIN


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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

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


@dataclass
class RefreshToken:
    id: UUID
    usuario_id: UUID
    token_hash: str
    expira_en: datetime
    revocado: bool = False
    user_agent: str | None = None
    ip: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def crear(
        usuario_id: UUID,
        token_hash: str,
        expira_en: datetime,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> "RefreshToken":
        return RefreshToken(
            id=uuid4(),
            usuario_id=usuario_id,
            token_hash=token_hash,
            expira_en=expira_en,
            user_agent=user_agent,
            ip=ip,
        )

    def esta_vigente(self, ahora: datetime | None = None) -> bool:
        ahora = ahora or datetime.now(timezone.utc)
        expira = self.expira_en
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)
        return not self.revocado and expira > ahora
