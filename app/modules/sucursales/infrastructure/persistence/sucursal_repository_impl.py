from uuid import UUID

from sqlalchemy import select, func, update, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sucursales.application.ports.sucursal_repository import SucursalRepository
from app.modules.sucursales.application.dtos import FiltroSucursales
from app.modules.sucursales.domain.entities import Sucursal
from app.modules.sucursales.infrastructure.persistence.orm_models import SucursalORM
from app.modules.sucursales.infrastructure.persistence.mappers import to_domain_sucursal
from app.shared.responses import Page, PageParams, Sort

_S = SucursalORM


class SqlAlchemySucursalRepository(SucursalRepository):
    _ORDEN = {
        "nombre": _S.nombre,
        "codigo": _S.codigo,
        "created_at": _S.created_at,
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, sucursal_id: UUID) -> Sucursal | None:
        orm = await self._db.get(_S, sucursal_id)
        return to_domain_sucursal(orm) if orm else None

    async def obtener_por_nombre(self, nombre: str) -> Sucursal | None:
        orm = (await self._db.execute(
            select(_S).where(func.lower(_S.nombre) == nombre.strip().lower())
        )).scalars().first()
        return to_domain_sucursal(orm) if orm else None

    async def obtener_por_codigo(self, codigo: str) -> Sucursal | None:
        orm = (await self._db.execute(
            select(_S).where(func.lower(_S.codigo) == codigo.strip().lower())
        )).scalars().first()
        return to_domain_sucursal(orm) if orm else None

    async def listar(
        self, filtro: FiltroSucursales, paginacion: PageParams, orden: Sort
    ) -> Page:
        cond = []
        if filtro.activo is not None:
            cond.append(_S.activo == filtro.activo)
        if filtro.tipo is not None:
            cond.append(_S.tipo == filtro.tipo.value)
        if filtro.sucursal_padre_id is not None:
            cond.append(_S.sucursal_padre_id == filtro.sucursal_padre_id)
        if filtro.busqueda:
            patron = f"%{filtro.busqueda.strip()}%"
            cond.append(or_(
                _S.nombre.ilike(patron),
                _S.codigo.ilike(patron),
                _S.direccion.ilike(patron),
                _S.telefono.ilike(patron),
            ))

        col = self._ORDEN.get(orden.field, _S.nombre)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(_S).where(*cond)
        )
        filas = (await self._db.execute(
            select(_S).where(*cond).order_by(orden_expr)
            .limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_sucursal(o) for o in filas], total=int(total or 0))

    async def crear(self, sucursal: Sucursal) -> Sucursal:
        self._db.add(SucursalORM(
            id=sucursal.id,
            codigo=sucursal.codigo,
            nombre=sucursal.nombre,
            tipo=sucursal.tipo.value,
            descripcion=sucursal.descripcion,
            imagen_fachada_key=sucursal.imagen_fachada_key,
            direccion=sucursal.direccion,
            colonia=sucursal.colonia,
            ciudad=sucursal.ciudad,
            estado=sucursal.estado,
            codigo_postal=sucursal.codigo_postal,
            pais=sucursal.pais,
            latitud=sucursal.latitud,
            longitud=sucursal.longitud,
            telefono=sucursal.telefono,
            email=sucursal.email,
            horario_apertura=sucursal.horario_apertura,
            horario_cierre=sucursal.horario_cierre,
            sucursal_padre_id=sucursal.sucursal_padre_id,
            permite_ventas=sucursal.permite_ventas,
            activo=sucursal.activo,
        ))
        await self._db.flush()
        return sucursal

    async def actualizar(self, sucursal: Sucursal) -> None:
        await self._db.execute(
            update(_S).where(_S.id == sucursal.id).values(
                codigo=sucursal.codigo,
                nombre=sucursal.nombre,
                tipo=sucursal.tipo.value,
                descripcion=sucursal.descripcion,
                imagen_fachada_key=sucursal.imagen_fachada_key,
                direccion=sucursal.direccion,
                colonia=sucursal.colonia,
                ciudad=sucursal.ciudad,
                estado=sucursal.estado,
                codigo_postal=sucursal.codigo_postal,
                pais=sucursal.pais,
                latitud=sucursal.latitud,
                longitud=sucursal.longitud,
                telefono=sucursal.telefono,
                email=sucursal.email,
                horario_apertura=sucursal.horario_apertura,
                horario_cierre=sucursal.horario_cierre,
                sucursal_padre_id=sucursal.sucursal_padre_id,
                permite_ventas=sucursal.permite_ventas,
                activo=sucursal.activo,
            )
        )
        await self._db.flush()

    async def tiene_usuarios_activos(self, sucursal_id: UUID) -> bool:
        # Lectura cross-tabla de `usuario` (no import de código de `usuarios`).
        total = await self._db.scalar(
            text(
                "SELECT count(*) FROM usuario "
                "WHERE sucursal_id = CAST(:sid AS uuid) AND activo IS TRUE"
            ),
            {"sid": str(sucursal_id)},
        )
        return bool(total)
