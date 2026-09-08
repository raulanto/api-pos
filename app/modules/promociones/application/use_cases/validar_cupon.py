from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.modules.promociones.application.ports.cupon_repository import CuponRepository
from app.modules.promociones.domain.entities import CuponUso
from app.modules.promociones.domain.exceptions import CuponNoEncontrado, CuponAgotado


class ValidarCuponUseCase:
    """Resuelve un código de cupón a su `promocion_id` validando vigencia y
    límites de uso. Lectura: no consume el cupón."""

    def __init__(self, repo: CuponRepository):
        self._repo = repo

    async def ejecutar(
        self, codigo: str, telefono: str | None = None,
        cliente_id: UUID | None = None, momento: datetime | None = None,
    ) -> UUID:
        momento = momento or datetime.now(timezone.utc)
        cupon = await self._repo.obtener_por_codigo(codigo)
        if cupon is None:
            raise CuponNoEncontrado(f"No hay un cupón con el código '{codigo}'.")
        cupon.exigir_vigente(momento)   # CuponVencido si no
        if cupon.max_usos_total is not None:
            if await self._repo.contar_usos(cupon.id) >= cupon.max_usos_total:
                raise CuponAgotado(f"El cupón {cupon.codigo} agotó sus usos.")
        if cupon.max_usos_por_persona is not None and (telefono or cliente_id):
            usados = await self._repo.contar_usos_persona(cupon.id, telefono, cliente_id)
            if usados >= cupon.max_usos_por_persona:
                raise CuponAgotado(
                    f"Ya usaste el cupón {cupon.codigo} el máximo de veces."
                )
        return cupon.promocion_id


class ConsumirCuponUseCase:
    """Registra el uso del cupón para una venta ya persistida. Bloquea la fila
    (`FOR UPDATE`) y re-chequea `max_usos_total` para que dos ventas simultáneas
    no pasen el límite."""

    def __init__(self, repo: CuponRepository):
        self._repo = repo

    async def ejecutar(
        self, codigo: str, venta_id: UUID, monto_descontado: Decimal,
        telefono: str | None = None, cliente_id: UUID | None = None,
    ) -> None:
        cupon = await self._repo.obtener_por_codigo(codigo, para_actualizar=True)
        if cupon is None:
            raise CuponNoEncontrado(f"No hay un cupón con el código '{codigo}'.")
        if cupon.max_usos_total is not None:
            if await self._repo.contar_usos(cupon.id) >= cupon.max_usos_total:
                raise CuponAgotado(f"El cupón {cupon.codigo} agotó sus usos.")
        await self._repo.registrar_uso(CuponUso.crear(
            cupon_id=cupon.id, venta_id=venta_id, monto_descontado=monto_descontado,
            telefono=telefono, cliente_id=cliente_id,
        ))
