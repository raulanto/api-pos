"""Cajas físicas (terminales): CRUD + abrir turno exige caja activa de la sucursal."""
import uuid
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import Caja
from app.modules.ventas.domain.exceptions import (
    CajaNoEncontrada, CajaInactiva,
)
from app.modules.ventas.application.use_cases.gestionar_terminales import (
    CrearCajaUseCase, CrearCajaInput, RenombrarCajaUseCase,
    DesactivarCajaUseCase, ReactivarCajaUseCase, NombreCajaEnUso,
)
from app.modules.ventas.application.use_cases.gestionar_caja import (
    AbrirCajaTurnoUseCase, AbrirCajaTurnoInput,
)

SUC = uuid.uuid4()


class _TerminalRepo:
    def __init__(self, cajas=None):
        self._c = {c.id: c for c in (cajas or [])}

    async def obtener_por_id(self, caja_id):
        return self._c.get(caja_id)

    async def listar(self, sucursal_id, incluir_inactivas=False):
        return [
            c for c in self._c.values()
            if c.sucursal_id == sucursal_id and (incluir_inactivas or c.activa)
        ]

    async def guardar(self, caja):
        self._c[caja.id] = caja

    async def actualizar(self, caja):
        self._c[caja.id] = caja

    async def nombre_en_uso(self, sucursal_id, nombre, excluir_id=None):
        return any(
            c.sucursal_id == sucursal_id and c.activa and c.id != excluir_id
            and c.nombre.lower() == nombre.strip().lower()
            for c in self._c.values()
        )


class _TurnoRepo:
    async def obtener_abierto_de_usuario(self, uid, sid):
        return None

    async def guardar(self, turno):
        pass

    async def guardar_denominaciones(self, turno_id, momento, conteos):
        pass


async def test_crear_caja_ok():
    repo = _TerminalRepo()
    caja = await CrearCajaUseCase(repo).ejecutar(CrearCajaInput(SUC, "Caja 1"))
    assert caja.nombre == "Caja 1" and caja.activa


async def test_nombre_duplicado_entre_activas_falla():
    repo = _TerminalRepo([Caja.crear(SUC, "Caja 1")])
    with pytest.raises(NombreCajaEnUso):
        await CrearCajaUseCase(repo).ejecutar(CrearCajaInput(SUC, " caja 1 "))


async def test_nombre_duplicado_con_la_otra_inactiva_ok():
    otra = Caja.crear(SUC, "Caja 1")
    otra.desactivar()
    repo = _TerminalRepo([otra])
    caja = await CrearCajaUseCase(repo).ejecutar(CrearCajaInput(SUC, "Caja 1"))
    assert caja.activa


async def test_renombrar_a_nombre_en_uso_falla():
    a = Caja.crear(SUC, "Caja 1")
    b = Caja.crear(SUC, "Caja 2")
    repo = _TerminalRepo([a, b])
    with pytest.raises(NombreCajaEnUso):
        await RenombrarCajaUseCase(repo).ejecutar(b.id, "Caja 1")


async def test_desactivar_y_reactivar():
    a = Caja.crear(SUC, "Caja 1")
    repo = _TerminalRepo([a])
    await DesactivarCajaUseCase(repo).ejecutar(a.id)
    assert not (await repo.obtener_por_id(a.id)).activa
    await ReactivarCajaUseCase(repo).ejecutar(a.id)
    assert (await repo.obtener_por_id(a.id)).activa


async def test_reactivar_choca_con_otra_activa_falla():
    a = Caja.crear(SUC, "Caja 1")
    a.desactivar()
    b = Caja.crear(SUC, "Caja 1")  # activa, mismo nombre
    repo = _TerminalRepo([a, b])
    with pytest.raises(NombreCajaEnUso):
        await ReactivarCajaUseCase(repo).ejecutar(a.id)


async def test_abrir_turno_exige_caja_activa_de_la_sucursal():
    caja = Caja.crear(SUC, "Caja 1")
    uc = AbrirCajaTurnoUseCase(
        _TurnoRepo(), None, None, _TerminalRepo([caja]),
    )
    turno = await uc.ejecutar(AbrirCajaTurnoInput(
        sucursal_id=SUC, caja_id=caja.id, usuario_id=uuid.uuid4(),
        saldo_inicial=Decimal("100"),
    ))
    assert turno.caja_id == caja.id and turno.esta_abierto


async def test_abrir_turno_caja_inactiva_falla():
    caja = Caja.crear(SUC, "Caja 1")
    caja.desactivar()
    uc = AbrirCajaTurnoUseCase(_TurnoRepo(), None, None, _TerminalRepo([caja]))
    with pytest.raises(CajaInactiva):
        await uc.ejecutar(AbrirCajaTurnoInput(
            sucursal_id=SUC, caja_id=caja.id, usuario_id=uuid.uuid4(),
            saldo_inicial=Decimal("0"),
        ))


async def test_abrir_turno_caja_de_otra_sucursal_falla():
    caja = Caja.crear(uuid.uuid4(), "Caja 1")
    uc = AbrirCajaTurnoUseCase(_TurnoRepo(), None, None, _TerminalRepo([caja]))
    with pytest.raises(CajaNoEncontrada):
        await uc.ejecutar(AbrirCajaTurnoInput(
            sucursal_id=SUC, caja_id=caja.id, usuario_id=uuid.uuid4(),
            saldo_inicial=Decimal("0"),
        ))
