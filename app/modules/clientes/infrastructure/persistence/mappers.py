from app.modules.clientes.domain.entities import (
    Cliente, MonederoCuenta, MonederoMovimiento,
)
from app.modules.clientes.domain.value_objects import TipoMovimientoMonedero
from app.modules.clientes.infrastructure.persistence.orm_models import (
    ClienteORM, MonederoCuentaORM, MonederoMovimientoORM,
)

def to_domain_cliente(orm: ClienteORM, includes: frozenset[str] = frozenset()) -> Cliente:
    cliente = Cliente(
        id=orm.id,
        sucursal_id=orm.sucursal_id,
        nombre=orm.nombre,
        email=orm.email,
        telefono=orm.telefono,
        rfc_identificacion=orm.rfc_identificacion,
        segmento=orm.segmento,
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
        segmento=entidad.segmento,
        limite_credito=entidad.limite_credito,
        saldo_credito=entidad.saldo_credito,
        activo=entidad.activo
    )


def to_domain_monedero_cuenta(orm: MonederoCuentaORM) -> MonederoCuenta:
    return MonederoCuenta(
        id=orm.id,
        telefono=orm.telefono,
        saldo=orm.saldo,
        activo=orm.activo,
        created_at=orm.created_at,
    )


def to_orm_monedero_cuenta(entidad: MonederoCuenta) -> MonederoCuentaORM:
    return MonederoCuentaORM(
        id=entidad.id,
        telefono=entidad.telefono,
        saldo=entidad.saldo,
        activo=entidad.activo,
    )


def to_domain_monedero_movimiento(orm: MonederoMovimientoORM) -> MonederoMovimiento:
    return MonederoMovimiento(
        id=orm.id,
        cuenta_id=orm.cuenta_id,
        tipo=TipoMovimientoMonedero(orm.tipo),
        monto=orm.monto,
        saldo_resultante=orm.saldo_resultante,
        venta_id=orm.venta_id,
        usuario_id=orm.usuario_id,
        motivo=orm.motivo,
        created_at=orm.created_at,
    )


def to_orm_monedero_movimiento(entidad: MonederoMovimiento) -> MonederoMovimientoORM:
    return MonederoMovimientoORM(
        id=entidad.id,
        cuenta_id=entidad.cuenta_id,
        tipo=entidad.tipo.value,
        monto=entidad.monto,
        saldo_resultante=entidad.saldo_resultante,
        venta_id=entidad.venta_id,
        usuario_id=entidad.usuario_id,
        motivo=entidad.motivo,
    )
