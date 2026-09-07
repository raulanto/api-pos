"""Casos de uso CRUD de promociones (fake repo en memoria)."""
import uuid
from decimal import Decimal

import pytest

from app.modules.promociones.domain.exceptions import (
    PromocionInvalida, PromocionNoEncontrada,
)
from app.modules.promociones.domain.entities import TipoPromocion
from app.modules.promociones.application.use_cases.gestionar_promociones import (
    CrearPromocionUseCase, CrearPromocionInput, ObjetivoInput,
    ActualizarPromocionUseCase, ActualizarPromocionInput,
    DesactivarPromocionUseCase,
)

PROD = uuid.uuid4()


class _Repo:
    def __init__(self, nombres=()):
        self._nombres = {n.lower() for n in nombres}
        self._por_id = {}
        self.creadas = []

    async def obtener_por_id(self, pid):
        return self._por_id.get(pid)

    async def existe_nombre(self, nombre, excluir_id=None):
        return nombre.strip().lower() in self._nombres

    async def crear(self, promo):
        self._por_id[promo.id] = promo
        self.creadas.append(promo)
        return promo

    async def actualizar(self, promo):
        self._por_id[promo.id] = promo


def _obj():
    return [ObjetivoInput(producto_id=PROD)]


async def test_crea_nxm_ok():
    repo = _Repo()
    promo = await CrearPromocionUseCase(repo).ejecutar(CrearPromocionInput(
        nombre="2x1", tipo=TipoPromocion.NXM, objetivos=_obj(), nxm_lleva=2, nxm_paga=1,
    ))
    assert promo in repo.creadas
    assert promo.nxm_lleva == 2


async def test_nxm_sin_params_falla():
    with pytest.raises(PromocionInvalida):
        await CrearPromocionUseCase(_Repo()).ejecutar(CrearPromocionInput(
            nombre="x", tipo=TipoPromocion.NXM, objetivos=_obj(),
        ))


async def test_nxm_lleva_menor_o_igual_paga_falla():
    with pytest.raises(PromocionInvalida):
        await CrearPromocionUseCase(_Repo()).ejecutar(CrearPromocionInput(
            nombre="x", tipo=TipoPromocion.NXM, objetivos=_obj(), nxm_lleva=2, nxm_paga=2,
        ))


async def test_porcentaje_fuera_de_rango_falla():
    with pytest.raises(PromocionInvalida):
        await CrearPromocionUseCase(_Repo()).ejecutar(CrearPromocionInput(
            nombre="x", tipo=TipoPromocion.PORCENTAJE, objetivos=_obj(),
            descuento_pct=Decimal("150"),
        ))


async def test_precio_fijo_negativo_falla():
    with pytest.raises(PromocionInvalida):
        await CrearPromocionUseCase(_Repo()).ejecutar(CrearPromocionInput(
            nombre="x", tipo=TipoPromocion.PRECIO_FIJO, objetivos=_obj(),
            precio_fijo=Decimal("-1"),
        ))


async def test_sin_objetivos_falla():
    with pytest.raises(PromocionInvalida):
        await CrearPromocionUseCase(_Repo()).ejecutar(CrearPromocionInput(
            nombre="x", tipo=TipoPromocion.PORCENTAJE, objetivos=[],
            descuento_pct=Decimal("10"),
        ))


async def test_nombre_duplicado_falla():
    with pytest.raises(PromocionInvalida):
        await CrearPromocionUseCase(_Repo(nombres=["2x1"])).ejecutar(CrearPromocionInput(
            nombre="2x1", tipo=TipoPromocion.NXM, objetivos=_obj(), nxm_lleva=2, nxm_paga=1,
        ))


async def test_actualizar_inexistente_falla():
    with pytest.raises(PromocionNoEncontrada):
        await ActualizarPromocionUseCase(_Repo()).ejecutar(
            ActualizarPromocionInput(promocion_id=uuid.uuid4(), prioridad=5)
        )


async def test_desactivar_marca_inactivo():
    repo = _Repo()
    promo = await CrearPromocionUseCase(repo).ejecutar(CrearPromocionInput(
        nombre="p", tipo=TipoPromocion.PORCENTAJE, objetivos=_obj(),
        descuento_pct=Decimal("10"),
    ))
    out = await DesactivarPromocionUseCase(repo).ejecutar(promo.id)
    assert out.activo is False
