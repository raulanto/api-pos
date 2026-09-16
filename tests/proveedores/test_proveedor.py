"""`Proveedor`: código único entre activos, crédito exige días, reactivar valida."""
import uuid

import pytest

from app.modules.proveedores.domain.entities import Proveedor
from app.modules.proveedores.domain.value_objects import TipoPersona, CondicionesPago
from app.modules.proveedores.domain.exceptions import (
    DiasCreditoRequerido, CodigoProveedorEnUso,
)
from app.modules.proveedores.application.use_cases.gestionar_proveedor import (
    CrearProveedorUseCase, CrearProveedorInput, ReactivarProveedorUseCase,
)


class _Repo:
    def __init__(self, proveedores=None):
        self._p = {p.id: p for p in (proveedores or [])}

    async def obtener_por_id(self, pid):
        return self._p.get(pid)

    async def buscar_por_codigo(self, codigo, solo_activos=True):
        for p in self._p.values():
            if p.codigo.lower() == codigo.strip().lower() and (not solo_activos or p.activo):
                return p
        return None

    async def guardar(self, proveedor):
        self._p[proveedor.id] = proveedor

    async def actualizar(self, proveedor):
        self._p[proveedor.id] = proveedor


def _input(**kw):
    base = dict(
        codigo="PROV-1", razon_social="Distribuidora XYZ", tipo_persona=TipoPersona.MORAL,
        condiciones_pago=CondicionesPago.CONTADO,
    )
    base.update(kw)
    return CrearProveedorInput(**base)


def test_credito_sin_dias_falla():
    with pytest.raises(DiasCreditoRequerido):
        Proveedor.crear(
            "P1", "Razon", TipoPersona.MORAL, CondicionesPago.CREDITO,
        )


def test_credito_con_dias_ok():
    p = Proveedor.crear("P1", "Razon", TipoPersona.MORAL, CondicionesPago.CREDITO, dias_credito=30)
    assert p.dias_credito == 30


def test_contado_ignora_dias_credito():
    p = Proveedor.crear(
        "P1", "Razon", TipoPersona.MORAL, CondicionesPago.CONTADO, dias_credito=30,
    )
    assert p.dias_credito is None


async def test_crear_codigo_duplicado_activo_falla():
    existente = Proveedor.crear("PROV-1", "Otro", TipoPersona.FISICA, CondicionesPago.CONTADO)
    repo = _Repo([existente])
    with pytest.raises(CodigoProveedorEnUso):
        await CrearProveedorUseCase(repo).ejecutar(_input())


async def test_crear_codigo_libre_de_uno_inactivo():
    existente = Proveedor.crear("PROV-1", "Otro", TipoPersona.FISICA, CondicionesPago.CONTADO)
    existente.desactivar()
    repo = _Repo([existente])
    nuevo = await CrearProveedorUseCase(repo).ejecutar(_input())
    assert nuevo.activo


async def test_reactivar_choca_con_otro_activo():
    a = Proveedor.crear("PROV-1", "A", TipoPersona.FISICA, CondicionesPago.CONTADO)
    a.desactivar()
    b = Proveedor.crear("PROV-1", "B", TipoPersona.FISICA, CondicionesPago.CONTADO)  # activo
    repo = _Repo([a, b])
    with pytest.raises(CodigoProveedorEnUso):
        await ReactivarProveedorUseCase(repo).ejecutar(a.id)


def test_actualizar_a_credito_sin_dias_falla():
    p = Proveedor.crear("P1", "Razon", TipoPersona.MORAL, CondicionesPago.CONTADO)
    with pytest.raises(DiasCreditoRequerido):
        p.actualizar(condiciones_pago=CondicionesPago.CREDITO)
