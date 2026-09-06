"""Fase 3: abrir turno de caja con la sucursal inactiva o permite_ventas=false."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.sucursales.domain.entities import Sucursal, TipoSucursal
from app.modules.ventas.domain.exceptions import SucursalNoOperativa
from app.modules.ventas.application.use_cases.gestionar_caja import (
    AbrirCajaTurnoUseCase, AbrirCajaTurnoInput,
)


def _suc(activo=True, permite_ventas=True) -> Sucursal:
    return Sucursal(
        id=uuid.uuid4(), nombre="Tienda", direccion="x", telefono="y",
        activo=activo, created_at=datetime.now(timezone.utc),
        tipo=TipoSucursal.TIENDA, permite_ventas=permite_ventas,
    )


class _SucRepo:
    def __init__(self, sucursal):
        self._s = sucursal

    async def obtener_por_id(self, sid):
        return self._s


class _CajaRepo:
    async def obtener_abierto_de_usuario(self, uid, sid):
        return None

    async def guardar(self, turno):
        pass


async def test_abrir_turno_sucursal_inactiva():
    uc = AbrirCajaTurnoUseCase(_CajaRepo(), None, _SucRepo(_suc(activo=False)))
    with pytest.raises(SucursalNoOperativa):
        await uc.ejecutar(AbrirCajaTurnoInput(
            sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
            saldo_inicial=Decimal("0"),
        ))


async def test_abrir_turno_permite_ventas_false():
    uc = AbrirCajaTurnoUseCase(_CajaRepo(), None, _SucRepo(_suc(permite_ventas=False)))
    with pytest.raises(SucursalNoOperativa):
        await uc.ejecutar(AbrirCajaTurnoInput(
            sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
            saldo_inicial=Decimal("0"),
        ))


async def test_abrir_turno_ok_si_operativa():
    uc = AbrirCajaTurnoUseCase(_CajaRepo(), None, _SucRepo(_suc()))
    turno = await uc.ejecutar(AbrirCajaTurnoInput(
        sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(), saldo_inicial=Decimal("0"),
    ))
    assert turno.esta_abierto


async def test_sin_sucursal_repo_no_valida():
    uc = AbrirCajaTurnoUseCase(_CajaRepo(), None, None)
    turno = await uc.ejecutar(AbrirCajaTurnoInput(
        sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(), saldo_inicial=Decimal("0"),
    ))
    assert turno.esta_abierto
