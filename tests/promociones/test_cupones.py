"""Cupones: vigencia y límites de uso (`ValidarCuponUseCase`)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.promociones.domain.entities import Cupon
from app.modules.promociones.domain.exceptions import (
    CuponNoEncontrado, CuponVencido, CuponAgotado,
)
from app.modules.promociones.application.use_cases.validar_cupon import (
    ValidarCuponUseCase, ConsumirCuponUseCase,
)

AHORA = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
PROMO = uuid.uuid4()


class _Repo:
    def __init__(self, cupon=None, usos=0, usos_persona=0):
        self._cupon = cupon
        self.usos = usos
        self.usos_persona = usos_persona
        self.registrados = []

    async def obtener_por_codigo(self, codigo, para_actualizar=False):
        return self._cupon

    async def contar_usos(self, cupon_id):
        return self.usos

    async def contar_usos_persona(self, cupon_id, telefono, cliente_id):
        return self.usos_persona

    async def registrar_uso(self, uso):
        self.registrados.append(uso)
        self.usos += 1


def _cupon(**kw):
    return Cupon.crear(codigo="BIENVENIDA", promocion_id=PROMO, **kw)


async def test_codigo_inexistente():
    with pytest.raises(CuponNoEncontrado):
        await ValidarCuponUseCase(_Repo(None)).ejecutar("NOPE", momento=AHORA)


async def test_vencido():
    c = _cupon(vigente_hasta=AHORA - timedelta(days=1))
    with pytest.raises(CuponVencido):
        await ValidarCuponUseCase(_Repo(c)).ejecutar("BIENVENIDA", momento=AHORA)


async def test_max_usos_total_agotado():
    c = _cupon(max_usos_total=1)
    with pytest.raises(CuponAgotado):
        await ValidarCuponUseCase(_Repo(c, usos=1)).ejecutar("BIENVENIDA", momento=AHORA)


async def test_max_usos_por_persona_agotado():
    c = _cupon(max_usos_por_persona=1)
    repo = _Repo(c, usos_persona=1)
    with pytest.raises(CuponAgotado):
        await ValidarCuponUseCase(repo).ejecutar(
            "BIENVENIDA", telefono="555", momento=AHORA,
        )


async def test_ok_devuelve_promocion_id():
    c = _cupon(max_usos_total=5)
    pid = await ValidarCuponUseCase(_Repo(c, usos=2)).ejecutar("BIENVENIDA", momento=AHORA)
    assert pid == PROMO


async def test_consumir_recuenta_y_registra():
    c = _cupon(max_usos_total=2)
    repo = _Repo(c, usos=1)
    await ConsumirCuponUseCase(repo).ejecutar(
        "BIENVENIDA", uuid.uuid4(), Decimal("30.00"), telefono="555",
    )
    assert len(repo.registrados) == 1
    # ahora sí agotado
    repo.usos = 2
    with pytest.raises(CuponAgotado):
        await ConsumirCuponUseCase(repo).ejecutar(
            "BIENVENIDA", uuid.uuid4(), Decimal("10.00"),
        )
