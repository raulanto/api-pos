from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.responses import Page, PageParams, Sort
from app.modules.agenda.application.ports.recurso_repository import RecursoRepository
from app.modules.agenda.application.ports.disponibilidad_repository import (
    DisponibilidadRepository,
)
from app.modules.agenda.application.ports.cita_repository import CitaRepository
from app.modules.agenda.application.dtos import FiltroCitas
from app.modules.agenda.domain.entities import (
    Recurso, EmpleadoServicio, HorarioBase, ExcepcionDisponibilidad, HorarioRecurso, Cita,
)
from app.modules.agenda.infrastructure.persistence.orm_models import (
    RecursoORM, EmpleadoServicioORM, DisponibilidadHorarioORM, DisponibilidadExcepcionORM,
    DisponibilidadRecursoORM, CitaORM, CitaAsignacionORM,
)
from app.modules.agenda.infrastructure.persistence.mappers import (
    to_domain_recurso, to_orm_recurso, to_domain_horario, to_orm_horario,
    to_domain_excepcion, to_orm_excepcion, to_domain_horario_recurso, to_orm_horario_recurso,
    to_domain_cita, to_orm_cita, to_orm_asignacion,
)

_OCUPA = ("asignada", "en_proceso")


class SqlAlchemyRecursoRepository(RecursoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, recurso_id: UUID) -> Recurso | None:
        orm = (await self._db.execute(
            select(RecursoORM).where(RecursoORM.id == recurso_id)
        )).scalar_one_or_none()
        return to_domain_recurso(orm) if orm else None

    async def listar(self, sucursal_id: UUID, incluir_inactivos: bool = False) -> list[Recurso]:
        cond = [RecursoORM.sucursal_id == sucursal_id]
        if not incluir_inactivos:
            cond.append(RecursoORM.activo.is_(True))
        filas = (await self._db.execute(
            select(RecursoORM).where(*cond).order_by(RecursoORM.nombre.asc())
        )).scalars().all()
        return [to_domain_recurso(o) for o in filas]

    async def guardar(self, recurso: Recurso) -> None:
        self._db.add(to_orm_recurso(recurso))
        await self._db.flush()

    async def actualizar(self, recurso: Recurso) -> None:
        await self._db.execute(
            update(RecursoORM).where(RecursoORM.id == recurso.id)
            .values(nombre=recurso.nombre, tipo=recurso.tipo, activo=recurso.activo)
        )
        await self._db.flush()

    async def nombre_en_uso(
        self, sucursal_id: UUID, nombre: str, excluir_id: UUID | None = None
    ) -> bool:
        cond = [
            RecursoORM.sucursal_id == sucursal_id,
            func.lower(RecursoORM.nombre) == nombre.strip().lower(),
            RecursoORM.activo.is_(True),
        ]
        if excluir_id is not None:
            cond.append(RecursoORM.id != excluir_id)
        return (await self._db.scalar(
            select(func.count()).select_from(RecursoORM).where(*cond)
        )) > 0

    async def recursos_libres_de(
        self, sucursal_id: UUID, inicio: datetime, fin: datetime,
    ) -> list[UUID]:
        ocupados = (
            select(CitaORM.recurso_id)
            .where(
                CitaORM.recurso_id.isnot(None),
                CitaORM.estado.in_(_OCUPA),
                CitaORM.fecha_hora_inicio < fin,
                CitaORM.fecha_hora_fin > inicio,
            )
        )
        filas = (await self._db.execute(
            select(RecursoORM.id).where(
                RecursoORM.sucursal_id == sucursal_id,
                RecursoORM.activo.is_(True),
                RecursoORM.id.notin_(ocupados),
            )
        )).scalars().all()
        return list(filas)


class SqlAlchemyDisponibilidadRepository(DisponibilidadRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    # --- empleado_servicio ---
    async def calificar_empleado(self, es: EmpleadoServicio) -> None:
        existente = (await self._db.execute(
            select(EmpleadoServicioORM).where(
                EmpleadoServicioORM.empleado_id == es.empleado_id,
                EmpleadoServicioORM.servicio_id == es.servicio_id,
            )
        )).scalar_one_or_none()
        if existente is not None:
            existente.activo = True
        else:
            self._db.add(EmpleadoServicioORM(
                id=es.id, empleado_id=es.empleado_id, servicio_id=es.servicio_id, activo=True,
            ))
        await self._db.flush()

    async def descalificar_empleado(self, empleado_id: UUID, servicio_id: UUID) -> None:
        await self._db.execute(
            update(EmpleadoServicioORM)
            .where(
                EmpleadoServicioORM.empleado_id == empleado_id,
                EmpleadoServicioORM.servicio_id == servicio_id,
            )
            .values(activo=False)
        )
        await self._db.flush()

    async def esta_calificado(self, empleado_id: UUID, servicio_id: UUID) -> bool:
        return (await self._db.scalar(
            select(func.count()).select_from(EmpleadoServicioORM).where(
                EmpleadoServicioORM.empleado_id == empleado_id,
                EmpleadoServicioORM.servicio_id == servicio_id,
                EmpleadoServicioORM.activo.is_(True),
            )
        )) > 0

    async def empleados_calificados(self, servicio_id: UUID) -> list[UUID]:
        filas = (await self._db.execute(
            select(EmpleadoServicioORM.empleado_id).where(
                EmpleadoServicioORM.servicio_id == servicio_id,
                EmpleadoServicioORM.activo.is_(True),
            )
        )).scalars().all()
        return list(filas)

    async def listar_servicios_de(self, empleado_id: UUID) -> list[EmpleadoServicio]:
        filas = (await self._db.execute(
            select(EmpleadoServicioORM).where(EmpleadoServicioORM.empleado_id == empleado_id)
        )).scalars().all()
        return [EmpleadoServicio(
            id=o.id, empleado_id=o.empleado_id, servicio_id=o.servicio_id,
            activo=o.activo, created_at=o.created_at,
        ) for o in filas]

    # --- disponibilidad_horario ---
    async def guardar_horario(self, horario: HorarioBase) -> None:
        self._db.add(to_orm_horario(horario))
        await self._db.flush()

    async def eliminar_horario(self, horario_id: UUID) -> None:
        orm = await self._db.get(DisponibilidadHorarioORM, horario_id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def horarios_de(
        self, empleado_ids: list[UUID], sucursal_id: UUID | None,
    ) -> dict[UUID, list[HorarioBase]]:
        out: dict[UUID, list[HorarioBase]] = {e: [] for e in empleado_ids}
        if not empleado_ids:
            return out
        cond = [DisponibilidadHorarioORM.empleado_id.in_(empleado_ids)]
        if sucursal_id is not None:
            cond.append(DisponibilidadHorarioORM.sucursal_id == sucursal_id)
        filas = (await self._db.execute(select(DisponibilidadHorarioORM).where(*cond))).scalars().all()
        for o in filas:
            out[o.empleado_id].append(to_domain_horario(o))
        return out

    # --- disponibilidad_excepcion ---
    async def guardar_excepcion(self, excepcion: ExcepcionDisponibilidad) -> None:
        self._db.add(to_orm_excepcion(excepcion))
        await self._db.flush()

    async def eliminar_excepcion(self, excepcion_id: UUID) -> None:
        orm = await self._db.get(DisponibilidadExcepcionORM, excepcion_id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def excepciones_de(
        self, empleado_ids: list[UUID], fecha: date,
    ) -> dict[UUID, list[ExcepcionDisponibilidad]]:
        out: dict[UUID, list[ExcepcionDisponibilidad]] = {e: [] for e in empleado_ids}
        if not empleado_ids:
            return out
        filas = (await self._db.execute(
            select(DisponibilidadExcepcionORM).where(
                DisponibilidadExcepcionORM.empleado_id.in_(empleado_ids),
                DisponibilidadExcepcionORM.fecha == fecha,
            )
        )).scalars().all()
        for o in filas:
            out[o.empleado_id].append(to_domain_excepcion(o))
        return out

    # --- disponibilidad_recurso ---
    async def guardar_horario_recurso(self, horario: HorarioRecurso) -> None:
        self._db.add(to_orm_horario_recurso(horario))
        await self._db.flush()

    async def horarios_del_recurso(self, recurso_id: UUID) -> list[HorarioRecurso]:
        filas = (await self._db.execute(
            select(DisponibilidadRecursoORM).where(DisponibilidadRecursoORM.recurso_id == recurso_id)
        )).scalars().all()
        return [to_domain_horario_recurso(o) for o in filas]

    # --- choques con otras citas ---
    async def empleados_ocupados_en(
        self, empleado_ids: list[UUID], inicio: datetime, fin: datetime,
    ) -> set[UUID]:
        if not empleado_ids:
            return set()
        filas = (await self._db.execute(
            select(CitaORM.empleado_id).where(
                CitaORM.empleado_id.in_(empleado_ids),
                CitaORM.estado.in_(_OCUPA),
                CitaORM.fecha_hora_inicio < fin,
                CitaORM.fecha_hora_fin > inicio,
            )
        )).scalars().all()
        return set(filas)


class SqlAlchemyCitaRepository(CitaRepository):
    _INCLUDES = {"cliente": CitaORM.cliente, "empleado": CitaORM.empleado}
    _ORDEN = {"fecha_hora_inicio": CitaORM.fecha_hora_inicio, "created_at": CitaORM.created_at}

    def __init__(self, db: AsyncSession):
        self._db = db

    def _opts(self, includes: frozenset[str]):
        return [selectinload(self._INCLUDES[i]) for i in includes if i in self._INCLUDES]

    async def obtener_por_id(
        self, cita_id: UUID, para_actualizar: bool = False,
    ) -> Cita | None:
        stmt = select(CitaORM).where(CitaORM.id == cita_id)
        if para_actualizar:
            stmt = stmt.with_for_update()
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_cita(orm) if orm else None

    async def guardar(self, cita: Cita) -> None:
        self._db.add(to_orm_cita(cita))
        await self._db.flush()

    async def actualizar(self, cita: Cita) -> None:
        await self._db.execute(
            update(CitaORM).where(CitaORM.id == cita.id).values(
                estado=cita.estado.value,
                empleado_id=cita.empleado_id,
                recurso_id=cita.recurso_id,
                motivo_cancelacion=cita.motivo_cancelacion,
                venta_detalle_id=cita.venta_detalle_id,
            )
        )
        # Las asignaciones son append-only: se actualiza la que ya existe (por
        # `id`) o se inserta la nueva (una reoferta reemplaza `cita.asignaciones`
        # en memoria con filas frescas, sin tocar el historial ya persistido).
        for a in cita.asignaciones:
            existente = await self._db.get(CitaAsignacionORM, a.id)
            if existente is None:
                self._db.add(to_orm_asignacion(a))
            else:
                existente.estado = a.estado.value
                existente.fecha_respuesta = a.fecha_respuesta
        await self._db.flush()

    async def listar(
        self, filtro: FiltroCitas, paginacion: PageParams, orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        cond = []
        if filtro.sucursal_id is not None:
            cond.append(CitaORM.sucursal_id == filtro.sucursal_id)
        if filtro.servicio_id is not None:
            cond.append(CitaORM.servicio_id == filtro.servicio_id)
        if filtro.empleado_id is not None:
            cond.append(CitaORM.empleado_id == filtro.empleado_id)
        if filtro.cliente_id is not None:
            cond.append(CitaORM.cliente_id == filtro.cliente_id)
        if filtro.estado is not None:
            cond.append(CitaORM.estado == filtro.estado.value)
        if filtro.desde is not None:
            cond.append(CitaORM.fecha_hora_inicio >= filtro.desde)
        if filtro.hasta is not None:
            cond.append(CitaORM.fecha_hora_inicio <= filtro.hasta)

        col = self._ORDEN.get(orden.field, CitaORM.fecha_hora_inicio)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(select(func.count()).select_from(CitaORM).where(*cond))
        filas = (await self._db.execute(
            select(CitaORM).options(*self._opts(includes)).where(*cond)
            .order_by(orden_expr).limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_cita(o, includes) for o in filas], total=int(total or 0))
