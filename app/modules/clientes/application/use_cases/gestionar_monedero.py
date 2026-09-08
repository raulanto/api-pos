from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.clientes.domain.entities import MonederoCuenta, MonederoMovimiento
from app.modules.clientes.domain.value_objects import TipoMovimientoMonedero
from app.modules.clientes.domain.exceptions import MonederoCuentaNoEncontrada
from app.modules.clientes.application.ports.monedero_repository import MonederoRepository
from app.shared.responses import Page, PageParams, Sort


async def _cargar(repo: MonederoRepository, telefono: str) -> MonederoCuenta:
    cuenta = await repo.obtener_por_telefono(telefono)
    if cuenta is None:
        raise MonederoCuentaNoEncontrada(
            f"No hay monedero para el teléfono {telefono}"
        )
    return cuenta


class ConsultarMonederoUseCase:
    def __init__(self, monedero_repo: MonederoRepository):
        self._repo = monedero_repo

    async def ejecutar(self, telefono: str) -> MonederoCuenta:
        return await _cargar(self._repo, telefono)


class ListarMovimientosMonederoUseCase:
    def __init__(self, monedero_repo: MonederoRepository):
        self._repo = monedero_repo

    async def ejecutar(self, telefono: str, paginacion: PageParams, orden: Sort) -> Page:
        cuenta = await _cargar(self._repo, telefono)
        return await self._repo.listar_movimientos(cuenta.id, paginacion, orden)


@dataclass
class AjustarMonederoInput:
    telefono: str
    monto: Decimal          # +/- ; nunca 0
    motivo: str | None = None
    usuario_id: UUID | None = None


class AjustarMonederoUseCase:
    """Ajuste manual del saldo (cargar saldo inicial, corrección). Crea la cuenta
    si no existe. Bloquea la fila para no pisar movimientos concurrentes."""

    def __init__(self, monedero_repo: MonederoRepository):
        self._repo = monedero_repo

    async def ejecutar(self, data: AjustarMonederoInput) -> MonederoCuenta:
        cuenta = await self._repo.obtener_por_telefono(data.telefono, para_actualizar=True)
        if cuenta is None:
            cuenta = MonederoCuenta.crear(data.telefono)
            await self._repo.crear_cuenta(cuenta)

        cuenta.ajustar(data.monto)
        await self._repo.guardar_saldo(cuenta)
        await self._repo.registrar_movimiento(MonederoMovimiento.crear(
            cuenta_id=cuenta.id, tipo=TipoMovimientoMonedero.AJUSTE, monto=data.monto,
            saldo_resultante=cuenta.saldo, usuario_id=data.usuario_id,
            motivo=data.motivo or "ajuste manual",
        ))
        return cuenta
