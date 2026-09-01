from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.infrastructure.persistence.orm_models import ClienteORM

def to_domain_cliente(orm: ClienteORM, includes: frozenset[str] = frozenset()) -> Cliente:
    cliente = Cliente(
        id=orm.id,
        sucursal_id=orm.sucursal_id,
        nombre=orm.nombre,
        email=orm.email,
        telefono=orm.telefono,
        rfc_identificacion=orm.rfc_identificacion,
        limite_credito=orm.limite_credito,
        saldo_credito=orm.saldo_credito,
        activo=orm.activo,
        created_at=orm.created_at
    )
    if "sucursal" in includes:
        cliente.sucursal = orm.sucursal
    return cliente

def to_orm_cliente(entidad: Cliente) -> ClienteORM:
    return ClienteORM(
        id=entidad.id,
        sucursal_id=entidad.sucursal_id,
        nombre=entidad.nombre,
        email=entidad.email,
        telefono=entidad.telefono,
        rfc_identificacion=entidad.rfc_identificacion,
        limite_credito=entidad.limite_credito,
        saldo_credito=entidad.saldo_credito,
        activo=entidad.activo
    )
