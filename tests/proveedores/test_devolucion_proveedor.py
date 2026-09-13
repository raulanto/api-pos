"""`DevolucionProveedor`: no se devuelve más que lo defectuoso, ciclo de estados."""
import uuid
from decimal import Decimal

import pytest

from app.modules.proveedores.domain.entities import DevolucionProveedor, DevolucionProveedorLinea
from app.modules.proveedores.domain.value_objects import ResultadoDevolucion, TipoResolucionDevolucion
from app.modules.proveedores.domain.exceptions import (
    CantidadDevolucionExcedeDefecto, TransicionDevolucionInvalida,
)
from app.modules.proveedores.application.use_cases.gestionar_devolucion import (
    CrearDevolucionUseCase, CrearDevolucionInput, LineaDevolucionInput,
)

PROVEEDOR = uuid.uuid4()
RECEPCION = uuid.uuid4()
PRODUCTO = uuid.uuid4()
USER = uuid.uuid4()
DETALLE = uuid.uuid4()


class _Detalle:
    def __init__(self, cantidad_defectuosa):
        self.producto_id = PRODUCTO
        self.cantidad_defectuosa = cantidad_defectuosa


class _RecepcionRepo:
    def __init__(self, defectuosa=Decimal("5")):
        self._detalle = _Detalle(defectuosa)

    async def obtener_linea(self, id_):
        return self._detalle


class _DevolucionRepo:
    def __init__(self, ya_devuelto=Decimal("0")):
        self._ya_devuelto = ya_devuelto
        self.guardadas = []

    async def cantidad_ya_devuelta(self, recepcion_detalle_id):
        return self._ya_devuelto

    async def guardar(self, devolucion):
        self.guardadas.append(devolucion)


async def test_devolver_mas_de_lo_defectuoso_falla():
    repo = _DevolucionRepo(ya_devuelto=Decimal("0"))
    recepcion_repo = _RecepcionRepo(defectuosa=Decimal("5"))
    uc = CrearDevolucionUseCase(repo, recepcion_repo)
    with pytest.raises(CantidadDevolucionExcedeDefecto):
        await uc.ejecutar(CrearDevolucionInput(
            proveedor_id=PROVEEDOR, recepcion_id=RECEPCION, creado_por=USER,
            lineas=[LineaDevolucionInput(recepcion_detalle_id=DETALLE, cantidad=Decimal("6"))],
        ))


async def test_devolver_sumando_lo_ya_devuelto_falla():
    repo = _DevolucionRepo(ya_devuelto=Decimal("3"))
    recepcion_repo = _RecepcionRepo(defectuosa=Decimal("5"))
    uc = CrearDevolucionUseCase(repo, recepcion_repo)
    with pytest.raises(CantidadDevolucionExcedeDefecto):
        await uc.ejecutar(CrearDevolucionInput(
            proveedor_id=PROVEEDOR, recepcion_id=RECEPCION, creado_por=USER,
            lineas=[LineaDevolucionInput(recepcion_detalle_id=DETALLE, cantidad=Decimal("3"))],
        ))


async def test_devolver_dentro_del_limite_ok():
    repo = _DevolucionRepo(ya_devuelto=Decimal("2"))
    recepcion_repo = _RecepcionRepo(defectuosa=Decimal("5"))
    uc = CrearDevolucionUseCase(repo, recepcion_repo)
    devolucion = await uc.ejecutar(CrearDevolucionInput(
        proveedor_id=PROVEEDOR, recepcion_id=RECEPCION, creado_por=USER,
        lineas=[LineaDevolucionInput(recepcion_detalle_id=DETALLE, cantidad=Decimal("3"))],
    ))
    assert len(repo.guardadas) == 1
    assert devolucion.lineas[0].cantidad == Decimal("3")


def _devolucion():
    return DevolucionProveedor.crear(
        PROVEEDOR, RECEPCION, USER,
        [DevolucionProveedorLinea.crear(DETALLE, PRODUCTO, Decimal("3"))],
    )


def test_ciclo_pendiente_enviada_cerrada():
    d = _devolucion()
    d.enviar()
    assert d.fecha_envio is not None
    d.cerrar(ResultadoDevolucion.RECHAZADA_PROVEEDOR)
    assert d.resultado == ResultadoDevolucion.RECHAZADA_PROVEEDOR
    assert d.tipo_resolucion is None


def test_cerrar_aceptada_sin_tipo_resolucion_falla():
    d = _devolucion()
    d.enviar()
    with pytest.raises(ValueError):
        d.cerrar(ResultadoDevolucion.ACEPTADA_PROVEEDOR)


def test_cerrar_aceptada_con_resolucion_ok():
    d = _devolucion()
    d.enviar()
    d.cerrar(ResultadoDevolucion.ACEPTADA_PROVEEDOR, TipoResolucionDevolucion.NOTA_CREDITO)
    assert d.tipo_resolucion == TipoResolucionDevolucion.NOTA_CREDITO


def test_enviar_dos_veces_falla():
    d = _devolucion()
    d.enviar()
    with pytest.raises(TransicionDevolucionInvalida):
        d.enviar()


def test_cerrar_sin_enviar_falla():
    d = _devolucion()
    with pytest.raises(TransicionDevolucionInvalida):
        d.cerrar(ResultadoDevolucion.RECHAZADA_PROVEEDOR)
