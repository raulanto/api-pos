from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.ventas.domain.entities import CajaTurno
from app.modules.ventas.domain.exceptions import (
    TurnoNoEncontrado, TurnoYaAbierto, TurnoYaCerrado, CierreTurnoNoPermitido,
    SucursalNoOperativa,
)
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.sucursales.application.ports.sucursal_repository import SucursalRepository


async def _exigir_sucursal_operativa(
    sucursal_repo: SucursalRepository | None, sucursal_id: UUID,
) -> None:
    """Bloquea la operación si la sucursal está inactiva o `permite_ventas=False`."""
    if sucursal_repo is None:
        return
    sucursal = await sucursal_repo.obtener_por_id(sucursal_id)
    if sucursal is None or not sucursal.activo or not sucursal.permite_ventas:
        raise SucursalNoOperativa(
            f"La sucursal {sucursal_id} no está operativa para ventas "
            "(inactiva o con permite_ventas=false)."
        )


@dataclass
class AbrirCajaTurnoInput:
    sucursal_id: UUID
    usuario_id: UUID
    saldo_inicial: Decimal


class AbrirCajaTurnoUseCase:
    def __init__(
        self,
        caja_repo: CajaTurnoRepository,
        event_port: EventPort | None = None,
        sucursal_repo: SucursalRepository | None = None,
    ):
        self._repo = caja_repo
        self._event_port = event_port
        self._sucursal_repo = sucursal_repo

    async def ejecutar(self, data: AbrirCajaTurnoInput) -> CajaTurno:
        await _exigir_sucursal_operativa(self._sucursal_repo, data.sucursal_id)
        abierto = await self._repo.obtener_abierto_de_usuario(data.usuario_id, data.sucursal_id)
        if abierto is not None:
            raise TurnoYaAbierto(
                f"El usuario ya tiene el turno {abierto.id} abierto; ciérralo antes de abrir otro."
            )

        turno = CajaTurno.abrir(
            sucursal_id=data.sucursal_id,
            usuario_id=data.usuario_id,
            saldo_inicial=data.saldo_inicial,
        )
        await self._repo.guardar(turno)

        if self._event_port is not None:
            await self._event_port.publicar("CajaTurnoAbierto", {
                "usuario_id": data.usuario_id,
                "modulo": "ventas",
                "accion": "abrir_turno",
                "entidad": "CajaTurno",
                "entidad_id": str(turno.id),
                "detalle": {
                    "sucursal_id": str(data.sucursal_id),
                    "saldo_inicial": str(turno.saldo_inicial),
                },
            })
        return turno


@dataclass
class CerrarCajaTurnoInput:
    caja_turno_id: UUID
    usuario_id: UUID
    saldo_final_declarado: Decimal
    # True para admin/gerente: puede cerrar turnos de otros usuarios.
    puede_cerrar_ajeno: bool = False


class CerrarCajaTurnoUseCase:
    def __init__(self, caja_repo: CajaTurnoRepository, event_port: EventPort | None = None):
        self._repo = caja_repo
        self._event_port = event_port

    async def ejecutar(self, data: CerrarCajaTurnoInput) -> CajaTurno:
        turno = await self._repo.obtener_por_id(data.caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {data.caja_turno_id}")
        if not turno.esta_abierto:
            raise TurnoYaCerrado(f"El turno {turno.id} ya está cerrado")
        if turno.usuario_id != data.usuario_id and not data.puede_cerrar_ajeno:
            raise CierreTurnoNoPermitido("Sólo el dueño del turno (o un gerente) puede cerrarlo")

        efectivo = await self._repo.total_efectivo_del_turno(turno.id)
        saldo_esperado = turno.saldo_inicial + efectivo
        turno.cerrar(data.saldo_final_declarado, saldo_esperado)
        await self._repo.actualizar(turno)

        if self._event_port is not None:
            await self._event_port.publicar("CajaTurnoCerrado", {
                "usuario_id": data.usuario_id,
                "modulo": "ventas",
                "accion": "cerrar_turno",
                "entidad": "CajaTurno",
                "entidad_id": str(turno.id),
                "detalle": {
                    "saldo_inicial": str(turno.saldo_inicial),
                    "total_efectivo": str(efectivo),
                    "saldo_esperado": str(saldo_esperado),
                    "saldo_final_declarado": str(turno.saldo_final_declarado),
                    "diferencia": str(turno.diferencia),
                },
            })
        return turno


class ObtenerTurnoActualUseCase:
    def __init__(self, caja_repo: CajaTurnoRepository):
        self._repo = caja_repo

    async def ejecutar(self, usuario_id: UUID, sucursal_id: UUID) -> CajaTurno:
        turno = await self._repo.obtener_abierto_de_usuario(usuario_id, sucursal_id)
        if turno is None:
            raise TurnoNoEncontrado("No tenés un turno de caja abierto en esta sucursal")
        return turno


@dataclass
class ResumenTurno:
    turno: CajaTurno
    total_efectivo: Decimal
    cantidad_ventas: int
    saldo_esperado: Decimal


class ObtenerResumenTurnoUseCase:
    """Resumen / arqueo del turno (sirve tanto abierto como cerrado)."""

    def __init__(self, caja_repo: CajaTurnoRepository):
        self._repo = caja_repo

    async def ejecutar(self, caja_turno_id: UUID) -> ResumenTurno:
        turno = await self._repo.obtener_por_id(caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {caja_turno_id}")
        efectivo = await self._repo.total_efectivo_del_turno(turno.id)
        cantidad = await self._repo.contar_ventas_del_turno(turno.id)
        return ResumenTurno(
            turno=turno,
            total_efectivo=efectivo,
            cantidad_ventas=cantidad,
            saldo_esperado=turno.saldo_inicial + efectivo,
        )
