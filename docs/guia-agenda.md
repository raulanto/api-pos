# Guía: agenda / venta de servicios con disponibilidad (para la app)

> Cómo implementar la pantalla de **citas**: agendar un servicio, ofertarlo a
> los empleados que lo atienden, que el empleado confirme, y cobrarlo.
> Todo cuelga de `/api/v1/agenda`; las terminales de servicio (recursos) y las
> citas viven ahí. Los **servicios** son productos (`/api/v1/inventario`,
> ver `docs/guia-alta-de-productos.md`). Al cobrar se emite una **venta**
> normal (ver `docs/guia-ventas-y-caja.md`).

---

## La idea en dos minutos

- Un **servicio** es un `producto` con `tipo=servicio` **y** `duracion_minutos`
  seteado (eso es lo que lo hace agendable; un servicio sin duración, como
  "flete", no entra a la agenda).
- Una **cita** = servicio + sucursal + fecha/hora + (opcional) cliente y
  recurso. Al crearla, el backend busca **quién puede atenderla** y le oferta a
  **todos los elegibles a la vez** (`por_asignar`). El primero que **acepta**
  se la queda; a los demás les queda **superada** (no es un rechazo).
- Si nadie está disponible → la cita queda `sin_empleado_disponible`. Un cajero
  puede reintentar la oferta (`/ofertar`) o **forzar** un empleado
  (`/asignar-manual`).
- Un **recurso** (silla, cabina, equipo) es opcional: sólo si el servicio
  `requiere_recurso`. Dos citas **no pueden** compartir el mismo recurso en el
  mismo horario — eso lo garantiza la base de datos, no hay forma de saltarlo.
  Dos citas **sí pueden** ofertarle al mismo empleado a la vez (es la cola); lo
  que no se permite es que el mismo empleado quede **asignado** a dos citas que
  se solapan.
- **Cobrar** una cita completada = un endpoint que arma una venta de una línea
  (el servicio) y la vincula a la cita. Caja, monedero, cupón y crédito
  funcionan igual que cualquier venta.

---

## Parte 0 — Puesta en marcha

```bash
uv run alembic upgrade head        # head: 3fa9b0f7d846
```

Agrega el rol **`empleado`** (staff que atiende servicios; no confundir con
`cajero`) y los permisos de agenda. Si tu negocio ya resuelve "quién atiende"
con el rol `cajero`, dale a ese rol los permisos `citas.ver_propias` /
`citas.responder_oferta` también (por SQL) y no uses el rol nuevo.

`APP_TIMEZONE` (`app/core/config.py`, default `America/Mexico_City`) es la
zona horaria en la que se interpretan los horarios/excepciones — igual que en
promociones.

---

## Parte 1 — Dar de alta un servicio agendable

Es un `producto` normal (`POST /api/v1/inventario/productos`) con estos campos
extra:

| Campo | Notas |
|---|---|
| `tipo` | `"servicio"` |
| `duracion_minutos` | **obligatorio para que se pueda agendar**. Cuánto dura la cita. |
| `tiempo_buffer_minutos` | default 0. Limpieza/preparación entre citas; se suma a la duración al calcular `fecha_hora_fin`. |
| `requiere_recurso` | si necesita silla/cabina/equipo además del empleado. |
| `disponibilidad_cruzada_activa` | si este servicio en particular admite ofertarle a empleados aunque su horario declarado sea de otra sucursal (ver Parte 5). |

```json
POST /api/v1/inventario/productos
{
  "sku": "SRV-CORTE", "nombre": "Corte de cabello", "categoria_id": "…",
  "unidad_medida": "servicio", "precio_venta": 250, "costo": 0, "impuesto_tasa": 0,
  "tipo": "servicio", "duracion_minutos": 30, "tiempo_buffer_minutos": 10,
  "requiere_recurso": true
}
```

Editar estos campos: mismo `PATCH /productos/{id}` de siempre; para volver
`duracion_minutos` a `null` (deja de ser agendable) mandá
`cambiar_duracion_minutos: true`.

---

## Parte 2 — Catálogo de agenda

### 2.1 Recursos (silla, cabina, equipo)

```
POST   /api/v1/agenda/recursos           { "nombre": "Silla 1", "tipo": "silla" }
GET    /api/v1/agenda/recursos?incluir_inactivos=false
PATCH  /api/v1/agenda/recursos/{id}      { "nombre": "…" }
DELETE /api/v1/agenda/recursos/{id}
PATCH  /api/v1/agenda/recursos/{id}/reactivar
```

Nombre único entre recursos **activos** de la sucursal. Permiso
`agenda.administrar`.

Si un recurso tiene horario propio distinto al de la sucursal (ej. una cabina
en mantenimiento cierto rango), se declara con:

```
POST /api/v1/agenda/recursos/{id}/horarios
{ "dia_semana": 2, "hora_inicio": "09:00", "hora_fin": "13:00" }
```

Sin filas = el recurso no tiene restricción propia (el único choque real sigue
siendo "no compartir horario con otra cita", garantizado siempre).

### 2.2 Qué empleados atienden qué servicio

```
POST   /api/v1/agenda/empleados/{empleado_id}/servicios?servicio_id=…
DELETE /api/v1/agenda/empleados/{empleado_id}/servicios/{servicio_id}
GET    /api/v1/agenda/empleados/{empleado_id}/servicios
```

`empleado_id` es un `usuario` (no hay una entidad "empleado" separada — el
staff que atiende citas es cualquier usuario del sistema, típicamente con rol
`empleado`). Permiso `agenda.administrar`.

### 2.3 Horario del empleado

```
POST   /api/v1/agenda/empleados/{empleado_id}/horarios
       { "sucursal_id": "…", "dia_semana": 0, "hora_inicio": "09:00", "hora_fin": "18:00" }
DELETE /api/v1/agenda/empleados/{empleado_id}/horarios/{horario_id}
GET    /api/v1/agenda/empleados/{empleado_id}/horarios
```

`dia_semana`: `0=lunes … 6=domingo`. Se pueden cargar varias filas el mismo día
(turno partido). El propio empleado puede **ver** su horario
(`citas.ver_propias`); sólo `agenda.administrar` lo edita.

### 2.4 Excepciones puntuales

```
POST /api/v1/agenda/empleados/{empleado_id}/excepciones
{ "fecha": "2026-12-25", "tipo": "bloqueo" }                         // no atiende todo el día
{ "fecha": "2026-12-24", "tipo": "bloqueo", "hora_inicio": "14:00", "hora_fin": "18:00" }  // se va temprano
{ "fecha": "2026-12-31", "tipo": "horario_especial", "hora_inicio": "09:00", "hora_fin": "13:00" } // horario reducido
```

- `bloqueo` sin horas = todo el día. Con horas = sólo ese rango.
- `horario_especial` **reemplaza** el horario base ese día (no se suma): la
  cita tiene que caber completa dentro de esas horas.

---

## Parte 3 — Crear y llevar una cita

### 3.1 Crear (ofertar automáticamente)

```
POST /api/v1/agenda/citas
{
  "servicio_id": "…",
  "fecha_hora_inicio": "2026-09-21T16:00:00Z",
  "cliente_id": "…",                // opcional
  "recurso_id": "…",                // opcional; si el servicio lo requiere y no lo mandás, se elige uno libre
  "disponibilidad_cruzada": false
}
```

Permiso `citas.gestionar`. El backend calcula `fecha_hora_fin` (duración +
buffer del servicio), busca los empleados **calificados**, **libres** de otra
cita que se solape y **dentro de su horario** (con excepciones aplicadas), y
crea una oferta (`cita_asignacion` en `ofrecida`) **para cada uno a la vez**.

Respuesta: la cita con `estado` y su lista de `asignaciones`. Si no hubo
elegibles, `estado: "sin_empleado_disponible"` y `asignaciones: []` (no es un
error — la cita se creó igual, para reintentar después).

### 3.2 El empleado responde su oferta

```
POST /api/v1/agenda/citas/{id}/aceptar
POST /api/v1/agenda/citas/{id}/rechazar
```

Permiso `citas.responder_oferta`; responde por el usuario autenticado (no se
manda `empleado_id`, el backend usa el token). El primero que **acepta** se
queda la cita (`estado: "asignada"`); a los demás candidatos con oferta viva se
les marca `superada`. Si **rechazás** y era la última oferta viva, la cita
pasa a `sin_empleado_disponible`.

> Aceptar vuelve a chequear que no tengas otra cita asignada que se solape en
> ese horario (`EmpleadoYaAsignado`) — puede pasar si aceptaste otra oferta
> justo antes. La oferta sigue viva para que otro candidato la tome.

### 3.3 Reintentar o forzar (cajero)

```
POST /api/v1/agenda/citas/{id}/ofertar          // reintenta la búsqueda de elegibles
POST /api/v1/agenda/citas/{id}/asignar-manual   { "empleado_id": "…" }  // salta la cola
```

Permiso `citas.gestionar`. `asignar-manual` igual valida que el empleado esté
calificado para el servicio y libre en ese horario.

### 3.4 El servicio en sí

```
POST /api/v1/agenda/citas/{id}/iniciar      // asignada -> en_proceso
POST /api/v1/agenda/citas/{id}/completar    // asignada o en_proceso -> completada
```

Permiso `citas.gestionar` **o** ser el empleado dueño de la cita.

### 3.5 Cancelar / no-show

```
PATCH /api/v1/agenda/citas/{id}/cancelar   { "motivo": "…" }   // terminal, permiso citas.gestionar
PATCH /api/v1/agenda/citas/{id}/no-show                        // sólo desde 'asignada'; manual, el cajero la marca
```

No hay detección automática de no-show (este backend no tiene jobs
programados): alguien tiene que marcarla.

### 3.6 Ver citas

```
GET /api/v1/agenda/citas?sucursal_id=&servicio_id=&empleado_id=&cliente_id=&estado=&desde=&hasta=
    &page=1&page_size=20&sort=fecha_hora_inicio:desc&include=cliente,empleado
GET /api/v1/agenda/citas/{id}
```

Con `citas.gestionar` ves todas; con sólo `citas.ver_propias` el filtro
`empleado_id` se fuerza al usuario autenticado (no podés ver las de otro).

---

## Parte 4 — Cobrar una cita

```
POST /api/v1/agenda/citas/{id}/facturar
{ "caja_turno_id": "…", "pagos": [{ "monto": 250, "metodo_pago": "efectivo" }] }
```

- Sólo una cita **`completada`** y sin facturar todavía (409
  `CitaYaFacturada` si ya tiene venta). Permiso `citas.gestionar`.
- Arma una venta de **una línea** (el servicio, al `precio_venta` vigente al
  momento de cobrar) y reusa el mismo motor de `POST /ventas/` — exige **turno
  de caja abierto**, funciona con crédito/monedero/cupón igual que cualquier
  venta. Soporta `Idempotency-Key`.
- Al confirmar, la línea (`detalle_venta.cita_id`) y la cita
  (`cita.venta_detalle_id`) quedan cruzadas — podés ir de una a la otra, pero
  `ventas` no sabe nada del modelo de `agenda` (es `agenda` el que llama al
  caso de uso de ventas, igual que hace `pedidos` al facturar).

---

## Parte 5 — Disponibilidad cruzada entre sucursales

Por default, un empleado sólo es candidato con el horario que declaró **para
la sucursal donde es la cita**. Si `producto.disponibilidad_cruzada_activa` es
`true` para ese servicio, mandando `"disponibilidad_cruzada": true` al crear la
cita, el backend ignora ese filtro y mira **todo** el horario declarado del
empleado (de cualquier sucursal) — útil para un especialista que viaja entre
locales. Si el servicio no tiene el flag activado, pedirlo da 400
`SucursalCruzadaNoPermitida`.

---

## Parte 6 — Los dos tipos de choque (para entender los errores)

| Choque | Tipo | Dónde se resuelve |
|---|---|---|
| **Recurso** (silla, cabina) en dos citas que se solapan | **Duro, físico** | Restricción nativa de Postgres (`EXCLUDE`); no hay forma de crear ese estado, ni por una carrera. Da `RecursoNoDisponible` (409). |
| **Empleado** ofertado a dos citas a la vez | No es un choque — es la cola (`por_asignar` no reserva nada) | — |
| **Empleado** *asignado* a dos citas que se solapan | Blando, de negocio | Se revalida en el momento de aceptar/asignar (`EmpleadoYaAsignado`, 409). Si se necesita en el futuro que sea un choque duro también, se agrega un `EXCLUDE` análogo sobre `empleado_id`. |

---

## Parte 7 — Permisos

| Permiso | Para qué | Roles por defecto |
|---|---|---|
| `agenda.administrar` | Alta/baja de recursos, calificar empleados, cargar horarios/excepciones | admin, gerente |
| `citas.gestionar` | Crear, listar todas, reofertar, asignar manual, iniciar/completar/cancelar/no-show, facturar cualquier cita | admin, gerente, cajero |
| `citas.ver_propias` | Ver sólo las citas propias (ofertadas o asignadas) | admin, gerente, cajero, **empleado** |
| `citas.responder_oferta` | Aceptar/rechazar una oferta propia; iniciar/completar la propia | admin, gerente, cajero, **empleado** |

---

## Parte 8 — Errores y qué significan

| Código | Error | Qué pasó |
|---|---|---|
| 400 | `ServicioNoAgendable` | El `servicio_id` no es `tipo=servicio` o no tiene `duracion_minutos` |
| 400 | `SucursalCruzadaNoPermitida` | Pediste `disponibilidad_cruzada` y el servicio no la tiene activada |
| 400 | `EmpleadoNoCalificado` | `asignar-manual` a un empleado sin `empleado_servicio` activo para ese servicio |
| 400 | `CitaNoOfertable` / `OfertaNoVigente` | Reofertar una cita que no está `por_asignar`/`sin_empleado_disponible`; responder una oferta ya superada/rechazada/aceptada |
| 400 | `TransicionCitaInvalida` | Ej. iniciar una cita que no está `asignada`, o cancelar/no-show fuera de lugar |
| 400 | `CitaNoFacturable` | Facturar una cita que no está `completada` |
| 403 | `AsignacionNoPropia` | Aceptar/rechazar una oferta que no es tuya |
| 404 | `RecursoNoEncontrado` / `CitaNoEncontrada` | El id no existe (o el recurso no es de esa sucursal) |
| 409 | `NombreRecursoEnUso` | Ya hay un recurso activo con ese nombre en la sucursal |
| 409 | `EmpleadoYaAsignado` | Al aceptar/asignar, el empleado ya tiene otra cita asignada que se solapa |
| 409 | `RecursoNoDisponible` | El recurso quedó ocupado por otra cita antes de confirmar (choque físico, lo frena la BD) |
| 409 | `CitaYaFacturada` | La cita ya tiene una venta vinculada |

---

## Parte 9 — Checklist para la pantalla de agenda

- [ ] Alta de servicio: en el formulario de producto, sección "Agenda" — duración, buffer, ¿requiere recurso?, ¿disponibilidad cruzada?
- [ ] Pantalla de catálogo: recursos por sucursal, qué empleados atienden qué servicio, horario semanal + excepciones por empleado
- [ ] Calendario/agenda del día: `GET /agenda/citas?desde=&hasta=&sucursal_id=`
- [ ] Crear cita: elegir servicio + horario → `POST /agenda/citas` → mostrar a quién se le ofertó
- [ ] Vista del empleado: sus ofertas pendientes (`citas.ver_propias` + `estado=por_asignar`, filtrando `asignaciones` en `ofrecida` para su `empleado_id`) con botones Aceptar/Rechazar
- [ ] Si queda `sin_empleado_disponible`: botón "reintentar" (`/ofertar`) o "asignar a mano" (`/asignar-manual`)
- [ ] Botones Iniciar/Completar en la vista del empleado y del cajero
- [ ] Cobrar: sólo visible si `estado=completada` y sin `venta_detalle_id` → `POST /citas/{id}/facturar`

---

## Fuera de alcance (por ahora)

- Sin generador de "huecos libres del día" para un calendario visual — el
  endpoint valida un horario puntual, no arma una grilla de slots.
- Sin política de cancelación aplicada (`politica_cancelacion_horas` /
  `penalizacion_cancelacion` se guardan pero no se usan todavía).
- Sin reportes de ocupación / tasa de no-show dedicados — se puede armar
  filtrando `GET /agenda/citas?estado=no_show`/`completada` mientras tanto.
- No-show es siempre manual (sin jobs programados en este backend).
