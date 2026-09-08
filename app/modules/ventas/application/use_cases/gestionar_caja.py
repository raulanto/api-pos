from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.ventas.domain.entities import (
    CajaMovimiento, CajaTurno, DenominacionConteo,
)
from app.modules.ventas.domain.value_objects import TipoMovimientoCaja
from app.modules.ventas.domain.exceptions import (
    TurnoNoEncontrado, TurnoYaAbierto, TurnoYaCerrado, CierreTurnoNoPermitido,
    SucursalNoOperativa, CajaNoEncontrada, CajaInactiva, DenominacionNoCuadra,
    MovimientoTurnoCerrado, ConciliacionNoPermitida,
)
from app.modules.ventas.application.dtos import FiltroTurnos
from app.modules.ventas.application.ports.caja_repository import (
    CajaRepository, CajaTurnoRepository,
)
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.sucursales.application.ports.sucursal_repository import SucursalRepository
from app.shared.responses import Page, PageParams, Sort

_CENT = Decimal("0.01")


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


def _exigir_denominaciones_cuadran(
    conteos: list[DenominacionConteo] | None, saldo: Decimal, momento: str,
) -> None:
    if not conteos:
        return
    suma = sum((c.subtotal for c in conteos), Decimal("0")).quantize(_CENT)
    if suma != Decimal(saldo).quantize(_CENT):
        raise DenominacionNoCuadra(
            f"El desglose de {momento} suma {suma}, pero el saldo declarado es {saldo}."
        )


@dataclass
class AbrirCajaTurnoInput:
    sucursal_id: UUID
    caja_id: UUID
    usuario_id: UUID
    saldo_inicial: Decimal
    denominaciones: list[DenominacionConteo] | None = None


class AbrirCajaTurnoUseCase:
    def __init__(
        self,
        caja_repo: CajaTurnoRepository,
        event_port: EventPort | None = None,
        sucursal_repo: SucursalRepository | None = None,
        terminal_repo: CajaRepository | None = None,
    ):
        self._repo = caja_repo
        self._event_port = event_port
        self._sucursal_repo = sucursal_repo
        self._terminal_repo = terminal_repo

    async def ejecutar(self, data: AbrirCajaTurnoInput) -> CajaTurno:
        await _exigir_sucursal_operativa(self._sucursal_repo, data.sucursal_id)

        if self._terminal_repo is not None:
            caja = await self._terminal_repo.obtener_por_id(data.caja_id)
            if caja is None or caja.sucursal_id != data.sucursal_id:
                raise CajaNoEncontrada(
                    f"No existe la caja {data.caja_id} en esta sucursal."
                )
            if not caja.activa:
                raise CajaInactiva(f"La caja '{caja.nombre}' está desactivada.")

        _exigir_denominaciones_cuadran(
            data.denominaciones, data.saldo_inicial, "apertura",
        )

        abierto = await self._repo.obtener_abierto_de_usuario(data.usuario_id, data.sucursal_id)
        if abierto is not None:
            raise TurnoYaAbierto(
                f"El usuario ya tiene el turno {abierto.id} abierto; ciérralo antes de abrir otro."
            )

        turno = CajaTurno.abrir(
            sucursal_id=data.sucursal_id,
            caja_id=data.caja_id,
            usuario_id=data.usuario_id,
            saldo_inicial=data.saldo_inicial,
        )
        try:
            await self._repo.guardar(turno)
        except IntegrityError:
            # Carrera: el índice único parcial (por caja y por usuario, WHERE
            # estado='abierto') frena un segundo turno abierto en la BD.
            raise TurnoYaAbierto(
                "Ya hay un turno abierto en esta caja o para este cajero."
            )

        if data.denominaciones:
            await self._repo.guardar_denominaciones(
                turno.id, "apertura", data.denominaciones,
            )

        if self._event_port is not None:
            await self._event_port.publicar("CajaTurnoAbierto", {
                "usuario_id": data.usuario_id,
                "modulo": "ventas",
                "accion": "abrir_turno",
                "entidad": "CajaTurno",
                "entidad_id": str(turno.id),
                "detalle": {
                    "sucursal_id": str(data.sucursal_id),
                    "caja_id": str(data.caja_id),
                    "saldo_inicial": str(turno.saldo_inicial),
                },
            })
        return turno


@dataclass
class CerrarCajaTurnoInput:
    caja_turno_id: UUID
    usuario_id: UUID
    saldo_final_declarado: Decimal
    nota_cierre: str | None = None
    denominaciones: list[DenominacionConteo] | None = None
    # True para admin/gerente: puede cerrar turnos de otros usuarios.
    puede_cerrar_ajeno: bool = False


class CerrarCajaTurnoUseCase:
    def __init__(
        self,
        caja_repo: CajaTurnoRepository,
        event_port: EventPort | None = None,
        umbral: Decimal | None = None,
    ):
        self._repo = caja_repo
        self._event_port = event_port
        self._umbral = umbral

    async def ejecutar(self, data: CerrarCajaTurnoInput) -> CajaTurno:
        turno = await self._repo.obtener_por_id(data.caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {data.caja_turno_id}")
        if not turno.esta_abierto:
            raise TurnoYaCerrado(f"El turno {turno.id} ya está cerrado")
        if turno.usuario_id != data.usuario_id and not data.puede_cerrar_ajeno:
            raise CierreTurnoNoPermitido(
                "Sólo el dueño del turno (o `caja.forzar_cierre`) puede cerrarlo"
            )

        _exigir_denominaciones_cuadran(
            data.denominaciones, data.saldo_final_declarado, "cierre",
        )

        efectivo = await self._repo.total_efectivo_del_turno(turno.id)
        dev_efectivo = await self._repo.total_devoluciones_efectivo_del_turno(turno.id)
        movimientos_neto = await self._repo.movimientos_neto_del_turno(turno.id)
        saldo_esperado = turno.saldo_inicial + efectivo - dev_efectivo + movimientos_neto
        turno.cerrar(
            data.saldo_final_declarado, saldo_esperado, self._umbral, data.nota_cierre,
        )
        await self._repo.actualizar(turno)

        if data.denominaciones:
            await self._repo.guardar_denominaciones(
                turno.id, "cierre", data.denominaciones,
            )

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
                    "movimientos_neto": str(movimientos_neto),
                    "saldo_esperado": str(saldo_esperado),
                    "saldo_final_declarado": str(turno.saldo_final_declarado),
                    "diferencia": str(turno.diferencia),
                    "estado": turno.estado,
                    "requiere_conciliacion": turno.requiere_conciliacion,
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
    total_devoluciones_efectivo: Decimal
    cantidad_ventas: int
    total_ingresos: Decimal
    total_retiros: Decimal
    total_gastos: Decimal
    movimientos_neto: Decimal
    saldo_esperado: Decimal
    denominaciones_apertura: list[DenominacionConteo] = field(default_factory=list)
    denominaciones_cierre: list[DenominacionConteo] = field(default_factory=list)


class ObtenerResumenTurnoUseCase:
    """Resumen / arqueo del turno (sirve tanto abierto como cerrado)."""

    def __init__(self, caja_repo: CajaTurnoRepository):
        self._repo = caja_repo

    async def ejecutar(self, caja_turno_id: UUID) -> ResumenTurno:
        turno = await self._repo.obtener_por_id(caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {caja_turno_id}")
        efectivo = await self._repo.total_efectivo_del_turno(turno.id)
        dev_efectivo = await self._repo.total_devoluciones_efectivo_del_turno(turno.id)
        cantidad = await self._repo.contar_ventas_del_turno(turno.id)
        por_tipo = await self._repo.movimientos_por_tipo(turno.id)
        ingresos = por_tipo.get("ingreso", Decimal("0"))
        retiros = por_tipo.get("retiro", Decimal("0"))
        gastos = por_tipo.get("gasto", Decimal("0"))
        neto = ingresos - retiros - gastos
        return ResumenTurno(
            turno=turno,
            total_efectivo=efectivo,
            total_devoluciones_efectivo=dev_efectivo,
            cantidad_ventas=cantidad,
            total_ingresos=ingresos,
            total_retiros=retiros,
            total_gastos=gastos,
            movimientos_neto=neto,
            saldo_esperado=turno.saldo_inicial + efectivo - dev_efectivo + neto,
            denominaciones_apertura=await self._repo.listar_denominaciones(turno.id, "apertura"),
            denominaciones_cierre=await self._repo.listar_denominaciones(turno.id, "cierre"),
        )


@dataclass
class RegistrarMovimientoCajaInput:
    caja_turno_id: UUID
    usuario_id: UUID
    tipo: TipoMovimientoCaja
    monto: Decimal
    motivo: str | None = None
    # True para admin/gerente: puede mover caja en turno ajeno.
    puede_operar_ajeno: bool = False


class RegistrarMovimientoCajaUseCase:
    def __init__(
        self, caja_repo: CajaTurnoRepository, event_port: EventPort | None = None,
    ):
        self._repo = caja_repo
        self._event_port = event_port

    async def ejecutar(self, data: RegistrarMovimientoCajaInput) -> CajaMovimiento:
        turno = await self._repo.obtener_por_id(data.caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {data.caja_turno_id}")
        if not turno.esta_abierto:
            raise MovimientoTurnoCerrado(
                f"El turno {turno.id} no está abierto: no se pueden registrar movimientos."
            )
        if turno.usuario_id != data.usuario_id and not data.puede_operar_ajeno:
            raise CierreTurnoNoPermitido(
                "Sólo el dueño del turno (o `caja.forzar_cierre`) puede mover su caja"
            )

        mov = CajaMovimiento.crear(
            caja_turno_id=turno.id, tipo=data.tipo, monto=data.monto,
            usuario_id=data.usuario_id, motivo=data.motivo,
        )
        await self._repo.registrar_movimiento(mov)

        if self._event_port is not None:
            await self._event_port.publicar("MovimientoCajaRegistrado", {
                "usuario_id": data.usuario_id,
                "modulo": "ventas",
                "accion": "movimiento_caja",
                "entidad": "CajaMovimiento",
                "entidad_id": str(mov.id),
                "detalle": {
                    "caja_turno_id": str(turno.id),
                    "tipo": mov.tipo.value,
                    "monto": str(mov.monto),
                    "motivo": mov.motivo,
                },
            })
        return mov


class ListarMovimientosCajaUseCase:
    def __init__(self, caja_repo: CajaTurnoRepository):
        self._repo = caja_repo

    async def ejecutar(self, caja_turno_id: UUID) -> list[CajaMovimiento]:
        turno = await self._repo.obtener_por_id(caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {caja_turno_id}")
        return await self._repo.listar_movimientos(caja_turno_id)


@dataclass
class ConciliarTurnoInput:
    caja_turno_id: UUID
    usuario_id: UUID
    puede_conciliar: bool = False
    nota: str | None = None


class ConciliarTurnoUseCase:
    """Autoriza (concilia) un turno cerrado con diferencia. Permiso
    `caja.autorizar_diferencia` (gerente/admin)."""

    def __init__(
        self, caja_repo: CajaTurnoRepository, event_port: EventPort | None = None,
    ):
        self._repo = caja_repo
        self._event_port = event_port

    async def ejecutar(self, data: ConciliarTurnoInput) -> CajaTurno:
        if not data.puede_conciliar:
            raise ConciliacionNoPermitida(
                "Se requiere el permiso `caja.autorizar_diferencia`."
            )
        turno = await self._repo.obtener_por_id(data.caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {data.caja_turno_id}")
        turno.conciliar(data.usuario_id, data.nota)
        await self._repo.actualizar(turno)

        if self._event_port is not None:
            await self._event_port.publicar("TurnoConciliado", {
                "usuario_id": data.usuario_id,
                "modulo": "ventas",
                "accion": "conciliar_turno",
                "entidad": "CajaTurno",
                "entidad_id": str(turno.id),
                "detalle": {
                    "caja_turno_id": str(turno.id),
                    "diferencia": str(turno.diferencia),
                    "nota_cierre": turno.nota_cierre,
                },
            })
        return turno


class ListarTurnosUseCase:
    """Histórico de turnos (arqueos, diferencias por cajero). Permiso
    `caja.ver_historico`."""

    def __init__(self, caja_repo: CajaTurnoRepository):
        self._repo = caja_repo

    async def ejecutar(
        self, filtro: FiltroTurnos, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar_turnos(filtro, paginacion, orden)


class EfectivoEnSucursalUseCase:
    def __init__(self, caja_repo: CajaTurnoRepository):
        self._repo = caja_repo

    async def ejecutar(self, sucursal_id: UUID) -> Decimal:
        return await self._repo.efectivo_en_sucursal(sucursal_id)
