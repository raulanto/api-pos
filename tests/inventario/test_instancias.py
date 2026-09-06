"""Tests de los casos de uso de instancia física abierta (envase destapado).

Dobles en memoria: sin BD ni movimientos reales. El "motor de movimiento" es un
fake que solo registra los `AplicarMovimientoInput` que recibiría.
"""
import uuid
from decimal import Decimal

import pytest

from app.modules.inventario.domain.entities import Producto, InstanciaAbierta
from app.modules.inventario.domain.value_objects import (
    TipoProducto, TipoMovimiento, EstadoInstancia,
)
from app.modules.inventario.domain.exceptions import (
    ProductoNoRastreaInstancias, CapacidadInstanciaInvalida, StockInsuficiente,
    SaldoInstanciaInsuficiente, InstanciaNoAbierta, InstanciaConfigInvalida,
)
from app.modules.inventario.application.use_cases.gestionar_instancias import (
    AbrirInstanciaUseCase, AbrirInstanciaInput,
    ConsumirInstanciaUseCase, ConsumirInstanciaInput,
    MermarInstanciaUseCase, MermarInstanciaInput,
    DescartarInstanciaUseCase, DescartarInstanciaInput,
    AjustarInstanciaUseCase, AjustarInstanciaInput,
)


def _producto(rastrea=True, cap="5", requiere_lote=False, permite_neg=False):
    p = Producto.crear(
        sku="AC-20W50", nombre="Aceite 20W-50", categoria_id=uuid.uuid4(),
        unidad_medida="L", precio_venta=Decimal("10"), costo=Decimal("6"),
        impuesto_tasa=Decimal("0"), tipo=TipoProducto.FRACCIONABLE,
        permite_stock_negativo=permite_neg, requiere_lote=requiere_lote,
        rastrea_instancia_abierta=rastrea,
        instancia_capacidad_default=Decimal(cap) if cap is not None else None,
    )
    return p


class _ProdRepo:
    def __init__(self, producto):
        self._p = producto

    async def obtener_por_id(self, pid, includes=frozenset()):
        return self._p


class _ExistRepo:
    def __init__(self, cantidad="20"):
        self._c = Decimal(cantidad) if cantidad is not None else None

    async def obtener(self, pid, sid):
        if self._c is None:
            return None
        return type("E", (), {"cantidad": self._c})()


class _InstRepo:
    def __init__(self, abiertas=None, saldo_abierto="0"):
        self.creadas = []
        self.actualizadas = []
        self._abiertas = abiertas or []
        self._saldo_abierto = Decimal(saldo_abierto)
        self._por_id = {i.id: i for i in (abiertas or [])}

    async def crear(self, inst):
        self.creadas.append(inst)
        self._por_id[inst.id] = inst

    async def obtener(self, iid):
        return self._por_id.get(iid)

    async def actualizar(self, inst):
        self.actualizadas.append(inst)

    async def listar_abiertas(self, pid, sid):
        return list(self._abiertas)

    async def saldo_abierto(self, pid, sid, lote_id=None):
        return self._saldo_abierto


class _UnidadRepo:
    def __init__(self, producto_id, factor="5"):
        self._pid = producto_id
        self._factor = Decimal(factor)

    async def obtener(self, uid):
        return type("U", (), {"producto_id": self._pid, "factor": self._factor})()


class _LoteRepo:
    def __init__(self, fefo=None):
        self._fefo = fefo or []

    async def lotes_fefo(self, pid, sid):
        return list(self._fefo)

    async def obtener(self, lid):
        return None


class _Motor:
    def __init__(self):
        self.calls = []

    async def ejecutar(self, data):
        self.calls.append(data)


class _Event:
    def __init__(self):
        self.eventos = []

    async def publicar(self, nombre, payload):
        self.eventos.append((nombre, payload))


# --------------------------------------------------------------------------- abrir
async def test_abrir_rechaza_producto_que_no_rastrea():
    p = _producto(rastrea=False)
    uc = AbrirInstanciaUseCase(_ProdRepo(p), _ExistRepo(), _InstRepo(), _UnidadRepo(p.id))
    with pytest.raises(ProductoNoRastreaInstancias):
        await uc.ejecutar(AbrirInstanciaInput(
            producto_id=p.id, sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
            capacidad=Decimal("5"),
        ))


async def test_abrir_xor_presentacion_y_capacidad():
    p = _producto()
    uc = AbrirInstanciaUseCase(_ProdRepo(p), _ExistRepo(), _InstRepo(), _UnidadRepo(p.id))
    with pytest.raises(CapacidadInstanciaInvalida):
        await uc.ejecutar(AbrirInstanciaInput(
            producto_id=p.id, sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
            producto_unidad_id=uuid.uuid4(), capacidad=Decimal("5"),
        ))


async def test_abrir_sin_capacidad_default_ni_presentacion():
    p = _producto(cap=None)
    uc = AbrirInstanciaUseCase(_ProdRepo(p), _ExistRepo(), _InstRepo(), _UnidadRepo(p.id))
    with pytest.raises(InstanciaConfigInvalida):
        await uc.ejecutar(AbrirInstanciaInput(
            producto_id=p.id, sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
        ))


async def test_abrir_cobertura_sellado_insuficiente():
    p = _producto()
    # total 4, ya hay 0 abierto -> sellado 4 < capacidad 5
    uc = AbrirInstanciaUseCase(
        _ProdRepo(p), _ExistRepo("4"), _InstRepo(), _UnidadRepo(p.id)
    )
    with pytest.raises(StockInsuficiente):
        await uc.ejecutar(AbrirInstanciaInput(
            producto_id=p.id, sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
            capacidad=Decimal("5"),
        ))


async def test_abrir_ok_desde_presentacion_publica_evento():
    p = _producto()
    inst_repo = _InstRepo()
    ev = _Event()
    uc = AbrirInstanciaUseCase(
        _ProdRepo(p), _ExistRepo("20"), inst_repo, _UnidadRepo(p.id, factor="5"),
        event_port=ev,
    )
    inst = await uc.ejecutar(AbrirInstanciaInput(
        producto_id=p.id, sucursal_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
        producto_unidad_id=uuid.uuid4(),
    ))
    assert inst.capacidad_inicial == Decimal("5")
    assert inst.saldo == Decimal("5")
    assert inst.estado is EstadoInstancia.ABIERTA
    assert inst_repo.creadas == [inst]
    assert ev.eventos and ev.eventos[0][0] == "InstanciaAbierta"


# ------------------------------------------------------------------------ consumir
def _instancia(saldo="5", estado=EstadoInstancia.ABIERTA):
    return InstanciaAbierta(
        id=uuid.uuid4(), producto_id=uuid.uuid4(), sucursal_id=uuid.uuid4(),
        capacidad_inicial=Decimal("5"), saldo=Decimal(saldo), estado=estado,
        abierta_por=uuid.uuid4(),
        abierta_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )


async def test_consumir_baja_saldo_y_registra_salida():
    inst = _instancia("5")
    repo = _InstRepo(abiertas=[inst])
    motor = _Motor()
    res = await ConsumirInstanciaUseCase(repo, motor).ejecutar(ConsumirInstanciaInput(
        instancia_id=inst.id, cantidad=Decimal("3.2"), usuario_id=uuid.uuid4(),
    ))
    assert res.saldo == Decimal("1.8")
    assert res.estado is EstadoInstancia.ABIERTA
    assert len(motor.calls) == 1
    mov = motor.calls[0]
    assert mov.tipo is TipoMovimiento.SALIDA
    assert mov.instancia_abierta_id == inst.id
    assert mov.cantidad == Decimal("3.2")
    assert repo.actualizadas == [inst]


async def test_consumir_hasta_cero_deja_agotada():
    inst = _instancia("2")
    res = await ConsumirInstanciaUseCase(_InstRepo(abiertas=[inst]), _Motor()).ejecutar(
        ConsumirInstanciaInput(
            instancia_id=inst.id, cantidad=Decimal("2"), usuario_id=uuid.uuid4(),
        )
    )
    assert res.saldo == Decimal("0")
    assert res.estado is EstadoInstancia.AGOTADA
    assert res.cerrada_at is not None


async def test_consumir_mas_que_saldo():
    inst = _instancia("1")
    with pytest.raises(SaldoInstanciaInsuficiente):
        await ConsumirInstanciaUseCase(_InstRepo(abiertas=[inst]), _Motor()).ejecutar(
            ConsumirInstanciaInput(
                instancia_id=inst.id, cantidad=Decimal("2"), usuario_id=uuid.uuid4(),
            )
        )


async def test_consumir_instancia_agotada():
    inst = _instancia("0", estado=EstadoInstancia.AGOTADA)
    with pytest.raises(InstanciaNoAbierta):
        await ConsumirInstanciaUseCase(_InstRepo(abiertas=[inst]), _Motor()).ejecutar(
            ConsumirInstanciaInput(
                instancia_id=inst.id, cantidad=Decimal("1"), usuario_id=uuid.uuid4(),
            )
        )


# -------------------------------------------------------------- merma / descartar
async def test_mermar_registra_merma():
    inst = _instancia("5")
    motor = _Motor()
    await MermarInstanciaUseCase(_InstRepo(abiertas=[inst]), motor).ejecutar(
        MermarInstanciaInput(
            instancia_id=inst.id, cantidad=Decimal("1"), usuario_id=uuid.uuid4(),
            motivo="derrame",
        )
    )
    assert inst.saldo == Decimal("4")
    assert motor.calls[0].tipo is TipoMovimiento.MERMA


async def test_descartar_merma_todo_el_remanente():
    inst = _instancia("1.8")
    motor = _Motor()
    res = await DescartarInstanciaUseCase(_InstRepo(abiertas=[inst]), motor).ejecutar(
        DescartarInstanciaInput(
            instancia_id=inst.id, usuario_id=uuid.uuid4(), motivo="contaminado",
        )
    )
    assert res.estado is EstadoInstancia.DESCARTADA
    assert res.saldo == Decimal("0")
    assert motor.calls[0].tipo is TipoMovimiento.MERMA
    assert motor.calls[0].cantidad == Decimal("1.8")


# ---------------------------------------------------------------------- ajustar
async def test_ajustar_a_la_baja_genera_merma():
    inst = _instancia("2.1")
    motor = _Motor()
    res = await AjustarInstanciaUseCase(_InstRepo(abiertas=[inst]), motor).ejecutar(
        AjustarInstanciaInput(
            instancia_id=inst.id, saldo_medido=Decimal("1.8"), usuario_id=uuid.uuid4(),
        )
    )
    assert res.saldo == Decimal("1.8")
    assert motor.calls[0].tipo is TipoMovimiento.MERMA
    assert motor.calls[0].cantidad == Decimal("0.3")


async def test_ajustar_al_alza_se_rechaza():
    inst = _instancia("1.8")
    with pytest.raises(CapacidadInstanciaInvalida):
        await AjustarInstanciaUseCase(_InstRepo(abiertas=[inst]), _Motor()).ejecutar(
            AjustarInstanciaInput(
                instancia_id=inst.id, saldo_medido=Decimal("2.5"),
                usuario_id=uuid.uuid4(),
            )
        )
