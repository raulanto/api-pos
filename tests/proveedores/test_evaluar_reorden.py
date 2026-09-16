"""`EvaluarReordenUseCase`: dispara pedidos cuando el stock cae bajo el mínimo."""
import uuid
from decimal import Decimal

from app.modules.proveedores.domain.entities import ProductoProveedor, PedidoProveedor
from app.modules.proveedores.application.use_cases.evaluar_reorden import EvaluarReordenUseCase

SUCURSAL = uuid.uuid4()
PROVEEDOR = uuid.uuid4()
PRODUCTO_BAJO = uuid.uuid4()
PRODUCTO_OK = uuid.uuid4()
USER = uuid.uuid4()


def _pp(producto_id, stock_minimo=Decimal("20")):
    return ProductoProveedor.crear(
        producto_id=producto_id, proveedor_id=PROVEEDOR, precio_compra=Decimal("10"),
        tiempo_entrega_dias=5, stock_minimo=stock_minimo, cantidad_reorden=Decimal("50"),
        es_proveedor_principal=True,
    )


class _PPRepo:
    def __init__(self, principales):
        self._principales = principales

    async def listar_principales_activos(self):
        return self._principales


class _PedidoRepo:
    def __init__(self):
        self.guardados = []
        self.actualizados = []
        self._borrador = None

    async def obtener_borrador_automatico(self, proveedor_id, sucursal_id):
        return self._borrador

    async def guardar(self, pedido):
        self.guardados.append(pedido)
        self._borrador = pedido

    async def actualizar(self, pedido):
        self.actualizados.append(pedido)


class _ExistenciaRepo:
    def __init__(self, stock: dict):
        self._stock = stock

    async def obtener(self, producto_id, sucursal_id):
        cantidad = self._stock.get(producto_id)
        if cantidad is None:
            return None
        return type("E", (), {"cantidad": cantidad})()


async def test_stock_bajo_el_minimo_genera_pedido():
    pp_repo = _PPRepo([_pp(PRODUCTO_BAJO)])
    pedido_repo = _PedidoRepo()
    existencia_repo = _ExistenciaRepo({PRODUCTO_BAJO: Decimal("5")})
    resultados = await EvaluarReordenUseCase(pp_repo, pedido_repo, existencia_repo).ejecutar(
        SUCURSAL, USER,
    )
    assert len(resultados) == 1
    assert resultados[0].fue_creado
    assert resultados[0].pedido.lineas[0].producto_id == PRODUCTO_BAJO


async def test_stock_por_encima_del_minimo_no_dispara():
    pp_repo = _PPRepo([_pp(PRODUCTO_OK)])
    pedido_repo = _PedidoRepo()
    existencia_repo = _ExistenciaRepo({PRODUCTO_OK: Decimal("100")})
    resultados = await EvaluarReordenUseCase(pp_repo, pedido_repo, existencia_repo).ejecutar(
        SUCURSAL, USER,
    )
    assert resultados == []


async def test_sin_existencia_se_asume_stock_cero():
    pp_repo = _PPRepo([_pp(PRODUCTO_BAJO)])
    pedido_repo = _PedidoRepo()
    existencia_repo = _ExistenciaRepo({})
    resultados = await EvaluarReordenUseCase(pp_repo, pedido_repo, existencia_repo).ejecutar(
        SUCURSAL, USER,
    )
    assert len(resultados) == 1


async def test_segunda_corrida_agrega_al_borrador_abierto():
    pp_repo = _PPRepo([_pp(PRODUCTO_BAJO)])
    pedido_repo = _PedidoRepo()
    existencia_repo = _ExistenciaRepo({PRODUCTO_BAJO: Decimal("5")})
    uc = EvaluarReordenUseCase(pp_repo, pedido_repo, existencia_repo)
    primero = await uc.ejecutar(SUCURSAL, USER)
    segundo = await uc.ejecutar(SUCURSAL, USER)
    assert primero[0].fue_creado
    assert not segundo[0].fue_creado
    assert segundo[0].pedido.lineas[0].cantidad_solicitada == Decimal("100")  # 50 + 50
