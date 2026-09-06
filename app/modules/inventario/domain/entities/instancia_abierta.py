from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.inventario.domain.value_objects import EstadoInstancia
from app.modules.inventario.domain.exceptions import (
    InstanciaNoAbierta, SaldoInstanciaInsuficiente, CapacidadInstanciaInvalida,
)


"""
    Entidad: una INSTANCIA FÍSICA ABIERTA de un producto fraccionable.

    Modela un envase concreto que se destapó para vender su contenido en
    fracciones de la unidad base (p. ej. un galón de 5 L abierto con 3.2 L
    restantes). El total en unidad base sigue en `existencia`; esta entidad solo
    rastrea *cuánto queda en este envase puntual* y de qué lote salió.

    @param id: ID de la instancia.
    @param producto_id: Producto (siempre en unidad base).
    @param sucursal_id: Sucursal donde está el envase.
    @param producto_unidad_id: Presentación de la que salió (opcional; define la
        capacidad si se abrió desde una presentación).
    @param lote_id: Lote del contenido (opcional; para trazar caducidad/costo).
    @param capacidad_inicial: Contenido del envase al abrirlo (unidad base, > 0).
    @param saldo: Contenido restante (0 <= saldo <= capacidad_inicial).
    @param estado: abierta | agotada | descartada.
    @param abierta_por: Usuario que la abrió.
    @param abierta_at: Momento de apertura.
    @param cerrada_at: Momento en que quedó agotada/descartada.
    @param motivo_cierre: Texto libre del cierre.
"""
@dataclass
class InstanciaAbierta:
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    capacidad_inicial: Decimal
    saldo: Decimal
    estado: EstadoInstancia
    abierta_por: UUID
    abierta_at: datetime
    producto_unidad_id: UUID | None = None
    lote_id: UUID | None = None
    cerrada_at: datetime | None = None
    motivo_cierre: str | None = None
    created_at: datetime = None  # type: ignore[assignment]

    @staticmethod
    def abrir(
        producto_id: UUID, sucursal_id: UUID, capacidad: Decimal, abierta_por: UUID,
        producto_unidad_id: UUID | None = None, lote_id: UUID | None = None,
    ) -> "InstanciaAbierta":
        if capacidad is None or capacidad <= 0:
            raise CapacidadInstanciaInvalida("La capacidad del envase debe ser > 0.")
        ahora = datetime.now(timezone.utc)
        return InstanciaAbierta(
            id=uuid4(),
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            capacidad_inicial=capacidad,
            saldo=capacidad,
            estado=EstadoInstancia.ABIERTA,
            abierta_por=abierta_por,
            abierta_at=ahora,
            producto_unidad_id=producto_unidad_id,
            lote_id=lote_id,
            created_at=ahora,
        )

    def _exigir_abierta(self) -> None:
        if self.estado is not EstadoInstancia.ABIERTA:
            raise InstanciaNoAbierta(
                f"La instancia {self.id} está {self.estado.value}; no admite operaciones."
            )

    def consumir(self, cantidad: Decimal, motivo: str = "agotada") -> None:
        """Baja `cantidad` del saldo. Si llega a 0, la instancia queda AGOTADA."""
        self._exigir_abierta()
        if cantidad is None or cantidad <= 0:
            raise SaldoInstanciaInsuficiente("La cantidad a consumir debe ser > 0.")
        if cantidad > self.saldo:
            raise SaldoInstanciaInsuficiente(
                f"La instancia {self.id} tiene {self.saldo}; se pidió {cantidad}."
            )
        self.saldo = self.saldo - cantidad
        if self.saldo == 0:
            self.estado = EstadoInstancia.AGOTADA
            self.cerrada_at = datetime.now(timezone.utc)
            self.motivo_cierre = motivo

    def descartar(self, motivo: str) -> Decimal:
        """Da de baja el envase con su remanente. Devuelve el saldo que hay que
        registrar como MERMA; deja la instancia en DESCARTADA con saldo 0."""
        self._exigir_abierta()
        remanente = self.saldo
        self.saldo = Decimal("0")
        self.estado = EstadoInstancia.DESCARTADA
        self.cerrada_at = datetime.now(timezone.utc)
        self.motivo_cierre = motivo
        return remanente

    def reponer(self, cantidad: Decimal) -> None:
        """Devuelve `cantidad` al saldo (anulación de venta). Reabre la instancia
        si estaba AGOTADA. Nunca supera `capacidad_inicial`."""
        if cantidad is None or cantidad <= 0:
            return
        if self.estado is EstadoInstancia.DESCARTADA:
            return  # un envase descartado no se resucita
        self.saldo = min(self.capacidad_inicial, self.saldo + cantidad)
        if self.estado is EstadoInstancia.AGOTADA and self.saldo > 0:
            self.estado = EstadoInstancia.ABIERTA
            self.cerrada_at = None
            self.motivo_cierre = None
