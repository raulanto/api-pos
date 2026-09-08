"""Adapta el monedero del módulo `clientes` al `MonederoPort` de ventas.

ponytail: la acumulación se calcula sobre el subtotal completo de la línea (no
resta la parte pagada con monedero). Si hace falta anti-doble-dipping, restar esa
fracción antes de acreditar.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ventas.application.ports.monedero_port import (
    MonederoPort, LineaAcumulacion,
)
from app.modules.clientes.domain.entities import MonederoCuenta, MonederoMovimiento
from app.modules.clientes.domain.value_objects import TipoMovimientoMonedero
from app.modules.clientes.domain.exceptions import SaldoMonederoInsuficiente
from app.modules.clientes.infrastructure.persistence.monedero_repository_impl import (
    SqlAlchemyMonederoRepository,
)
from app.modules.inventario.infrastructure.persistence.repositories.producto import (
    SqlAlchemyProductoRepository,
)
from app.modules.inventario.infrastructure.persistence.repositories.unidad import (
    SqlAlchemyProductoUnidadRepository,
)

_CENT = Decimal("0.01")


class MonederoPortImpl(MonederoPort):
    def __init__(self, db: AsyncSession):
        self._repo = SqlAlchemyMonederoRepository(db)
        self._producto_repo = SqlAlchemyProductoRepository(db)
        self._unidad_repo = SqlAlchemyProductoUnidadRepository(db)
        self._cache_prod: dict[UUID, object] = {}
        self._cache_unidad: dict[UUID, object] = {}

    # -- cálculo de la acumulación ------------------------------------------- #
    async def _config(self, producto_id: UUID, producto_unidad_id: UUID | None):
        """(pct, monto) a aplicar: la presentación reemplaza al producto si tiene
        alguno de los dos seteado."""
        if producto_unidad_id is not None:
            if producto_unidad_id not in self._cache_unidad:
                self._cache_unidad[producto_unidad_id] = await self._unidad_repo.obtener(
                    producto_unidad_id
                )
            u = self._cache_unidad[producto_unidad_id]
            if u is not None and (u.monedero_pct is not None or u.monedero_monto is not None):
                return u.monedero_pct, u.monedero_monto
        if producto_id not in self._cache_prod:
            self._cache_prod[producto_id] = await self._producto_repo.obtener_por_id(producto_id)
        p = self._cache_prod[producto_id]
        if p is None:
            return None, None
        return p.monedero_pct, p.monedero_monto

    async def _monto_linea(self, linea: LineaAcumulacion) -> Decimal:
        pct, monto = await self._config(linea.producto_id, linea.producto_unidad_id)
        if pct is not None and pct > 0:
            return (linea.subtotal * pct / Decimal("100")).quantize(_CENT)
        if monto is not None and monto > 0:
            return (linea.cantidad * monto).quantize(_CENT)
        return Decimal("0")

    async def calcular_acumulacion(self, lineas: list[LineaAcumulacion]) -> Decimal:
        total = Decimal("0")
        for l in lineas:
            total += await self._monto_linea(l)
        return total.quantize(_CENT)

    # -- helpers de cuenta -------------------------------------------------- #
    async def _cuenta_para_acreditar(self, telefono: str) -> MonederoCuenta:
        cuenta = await self._repo.obtener_por_telefono(telefono, para_actualizar=True)
        if cuenta is None:
            cuenta = MonederoCuenta.crear(telefono)
            await self._repo.crear_cuenta(cuenta)
        return cuenta

    async def _movimiento(self, cuenta, tipo, monto, venta_id, usuario_id, motivo=None):
        await self._repo.guardar_saldo(cuenta)
        await self._repo.registrar_movimiento(MonederoMovimiento.crear(
            cuenta_id=cuenta.id, tipo=tipo, monto=monto,
            saldo_resultante=cuenta.saldo, venta_id=venta_id,
            usuario_id=usuario_id, motivo=motivo,
        ))

    # -- API del puerto -------------------------------------------------- #
    async def acumular(
        self, telefono: str, lineas: list[LineaAcumulacion],
        venta_id: UUID, usuario_id: UUID,
    ) -> Decimal:
        total = await self.calcular_acumulacion(lineas)
        if total <= 0:
            return Decimal("0")
        cuenta = await self._cuenta_para_acreditar(telefono)
        cuenta.acreditar(total)
        await self._movimiento(
            cuenta, TipoMovimientoMonedero.ACUMULACION, total, venta_id, usuario_id,
        )
        return total

    async def consumir(
        self, telefono: str, monto: Decimal, venta_id: UUID, usuario_id: UUID,
    ) -> None:
        cuenta = await self._repo.obtener_por_telefono(telefono, para_actualizar=True)
        if cuenta is None:
            raise SaldoMonederoInsuficiente(
                f"El teléfono {telefono} no tiene monedero."
            )
        cuenta.debitar(monto)   # lanza SaldoMonederoInsuficiente si no alcanza
        await self._movimiento(
            cuenta, TipoMovimientoMonedero.CONSUMO, monto, venta_id, usuario_id,
        )

    async def reintegrar(
        self, telefono: str, monto: Decimal, venta_id: UUID, usuario_id: UUID,
        motivo: str,
    ) -> None:
        if monto <= 0:
            return
        cuenta = await self._cuenta_para_acreditar(telefono)
        cuenta.acreditar(monto)
        await self._movimiento(
            cuenta, TipoMovimientoMonedero.REVERSO_CONSUMO, monto, venta_id,
            usuario_id, motivo,
        )

    async def revertir_venta(
        self, telefono: str | None, venta_id: UUID, usuario_id: UUID,
    ) -> None:
        if not telefono:
            return
        movs = await self._repo.movimientos_de_venta(venta_id)
        movs = [
            m for m in movs
            if m.tipo in (TipoMovimientoMonedero.ACUMULACION, TipoMovimientoMonedero.CONSUMO)
        ]
        if not movs:
            return
        cuenta = await self._repo.obtener_por_telefono(telefono, para_actualizar=True)
        if cuenta is None:
            return
        for m in movs:
            if m.tipo == TipoMovimientoMonedero.ACUMULACION:
                quita = cuenta.debitar_hasta(m.monto)
                if quita > 0:
                    await self._movimiento(
                        cuenta, TipoMovimientoMonedero.REVERSO_ACUMULACION, quita,
                        venta_id, usuario_id, "anulación de venta",
                    )
            else:  # CONSUMO
                cuenta.acreditar(m.monto)
                await self._movimiento(
                    cuenta, TipoMovimientoMonedero.REVERSO_CONSUMO, m.monto,
                    venta_id, usuario_id, "anulación de venta",
                )
