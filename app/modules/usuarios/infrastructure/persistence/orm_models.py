import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

# Tabla intermedia N:M (rol - permiso)
rol_permiso_table = Table(
    "rol_permiso",
    Base.metadata,
    Column("rol_id", PGUUID(as_uuid=True), ForeignKey("rol.id"), primary_key=True),
    Column("permiso_id", PGUUID(as_uuid=True), ForeignKey("permiso.id"), primary_key=True),
)

class SucursalORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sucursal"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    direccion = Column(String(255), nullable=False)
    telefono = Column(String(20), nullable=False)

class PermisoORM(Base):
    __tablename__ = "permiso"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(50), unique=True, nullable=False)
    descripcion = Column(String(255), nullable=False)

class RolORM(Base):
    __tablename__ = "rol"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(50), unique=True, nullable=True, index=True)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(String(255), nullable=False)
    permisos = relationship("PermisoORM", secondary=rol_permiso_table)

class UsuarioORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "usuario"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=True, index=True)
    rol_id = Column(PGUUID(as_uuid=True), ForeignKey("rol.id"), nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    sucursal = relationship("SucursalORM")
    rol = relationship("RolORM")

class RefreshTokenORM(Base):
    __tablename__ = "refresh_token"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False, index=True)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    revocado = Column(Boolean, default=False, nullable=False)
    user_agent = Column(String(255), nullable=True)
    ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    usuario = relationship("UsuarioORM")
