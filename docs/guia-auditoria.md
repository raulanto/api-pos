# Guía: Módulo de Auditoría (para la app y desarrolladores)

> Cómo funciona el sistema de trazabilidad y logs de auditoría en la API,
> qué información se almacena, los eventos capturados por cada módulo y
> cómo consultar e integrar la auditoría.
> Todo cuelga del endpoint `/api/v1/auditoria`.

---

## ⚡ La idea en dos minutos

- Todo evento de importancia (crear/editar productos, usuarios, clientes, ventas, arqueos de caja, ajustes de stock, etc.) emite un **evento de dominio in-process** a través del `event_bus`.
- El listener del módulo `auditoria` escucha estos eventos y los persiste automáticamente en la tabla `log_auditoria` usando la **misma transacción de la base de datos** (`AsyncSession`). Si una operación falla o hace *rollback*, la auditoría tampoco se guarda (consistencia total).
- Toda acción auditada registra **quién la realizó** (`usuario_id`), en **qué módulo** (`modulo`), **qué acción** (`accion`), sobre **qué entidad** (`entidad` y `entidad_id`), junto con un **desglose en JSON** (`detalle`) y la **marca de tiempo** (`fecha`).
- La consulta de auditoría está protegida por el permiso **`auditoria.leer`**.

---

## 🗄️ Modelo de Datos (`log_auditoria`)

Cada registro de auditoría contiene la siguiente información:

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `UUID` | Identificador único del log. |
| `usuario_id` | `UUID` | ID del usuario autenticado que ejecutó la acción. Se puede expandir con `?include=usuario`. |
| `modulo` | `varchar(50)` | Nombre del módulo (`ventas`, `caja`, `inventario`, `usuarios`, `clientes`, `proveedores`, `promociones`, `sucursales`, `pedidos`). |
| `accion` | `varchar(100)` | Código de la acción (ej. `crear_producto`, `VentaCreada`, `CajaTurnoAbierto`). |
| `entidad` | `varchar(100)` | Nombre de la entidad afectada (ej. `Producto`, `Venta`, `Cliente`). |
| `entidad_id` | `varchar(100)` | ID en formato texto de la entidad modificada. |
| `detalle` | `JSONB` | Objeto con datos clave del evento (ej. `{ "sku": "PROD-01", "nombre": "Camisa" }`). |
| `ip_address` | `varchar(45)` | Dirección IP de la solicitud (opcional / nullable). |
| `fecha` | `TIMESTAMPTZ` | Timestamp en UTC en que se registró la operación. |

---

## 📡 Lista de Eventos Auditados por Módulo

El sistema captura automáticamente los siguientes eventos:

### 🛒 Ventas
- `VentaCreada`: Registro de nueva venta en caja.
- `VentaAnulada`: Anulación completa de venta.
- `DescuentoManualAplicado`: Aplicación de descuento manual en la línea o total.

### 💰 Caja
- `CajaTurnoAbierto`: Apertura de turno de caja con saldo inicial.
- `CajaTurnoCerrado`: Cierre de turno de caja con arqueo final y declaración de efectivo.
- `MovimientoCajaRegistrado`: Ingreso, retiro o gasto registrado en el cajón.
- `TurnoConciliado`: Autorización gerencial de turno cerrado con diferencia.

### 📦 Inventario
- `ProductoCreado`: Alta de nuevo producto.
- `ProductoEditado`: Modificación de precios, stock, categoría o datos de producto.
- `ProductoDesactivado`: Baja lógica de un producto.
- `CategoriaCreada`: Alta de categoría.
- `CategoriaEditada`: Edición de categoría.
- `MovimientoInventarioRegistrado`: Entradas, salidas o ajustes de stock.
- `TransferenciaInventarioRegistrada`: Traspaso de mercadería entre sucursales.

### 👥 Usuarios
- `UsuarioCreado`: Registro de nuevo usuario.
- `UsuarioEditado`: Cambio de nombre, email o sucursal.
- `UsuarioDesactivado`: Desactivación de cuenta de usuario.
- `UsuarioReactivado`: Reactivación de cuenta.

### 🤝 Clientes
- `ClienteCreado`: Registro de cliente.
- `ClienteEditado`: Actualización de datos de cliente.

### 🏭 Proveedores
- `ProveedorCreado`: Alta de proveedor.
- `ProveedorEditado`: Edición de proveedor.

### 🏷️ Promociones
- `PromocionCreada`: Configuración de nueva promoción o descuento.
- `PromocionEditada`: Modificación de reglas o vigencias.

### 🏢 Sucursales
- `SucursalCreada`: Alta de sucursal.
- `SucursalEditada`: Modificación de sucursal.

### 📋 Pedidos
- `PedidoCreado`: Registro de pedido de cliente (presencial, delivery o web).
- `PedidoConfirmado`: Confirmación del pedido con snapshot de precio congelado.
- `PedidoCancelado`: Cancelación de pedido.
- `PedidoReabierto`: Reapertura de pedido cancelado o modificado.
- `PedidoEntregaActualizada`: Avance en estado de entrega o asignación de repartidor.
- `PedidoAnticipoRegistrado`: Abono o anticipo registrado para el pedido.
- `PedidoServiciosAsignados`: Asignación de personal a líneas de servicios.
- `PedidoFacturado`: Conversión del pedido confirmado en Venta de caja.


---

## 🔍 Consulta de Auditoría (API Endpoints)

### 1. Listar Logs con Filtros y Paginación

```
GET /api/v1/auditoria
```

#### Parámetros Query Admitidos:
- `usuario_id` (`UUID`): Filtrar por el usuario que realizó la acción.
- `modulo` (`string`): Filtrar por módulo (ej. `ventas`, `inventario`).
- `accion` (`string`): Filtrar por acción específica (ej. `crear_producto`).
- `entidad` (`string`): Filtrar por entidad (ej. `Producto`).
- `entidad_id` (`string`): Filtrar por el ID de la entidad específica.
- `desde` (`datetime ISO8601`): Fecha inicio del rango (ej. `2026-09-01T00:00:00Z`).
- `hasta` (`datetime ISO8601`): Fecha fin del rango.
- `page` (`int`, default 1): Número de página.
- `page_size` (`int`, default 20): Registros por página.
- `sort` (`string`, default `fecha:desc`): Ordenamiento. Campos permitidos: `fecha`, `created_at`, `modulo`, `accion`.
- `include` (`string`): Expansión de relaciones (`include=usuario`).

#### Ejemplo de Petición:
```http
GET /api/v1/auditoria?modulo=inventario&page=1&page_size=20&sort=created_at:desc&include=usuario
```

#### Ejemplo de Respuesta `200 OK`:
```json
{
  "success": true,
  "data": [
    {
      "id": "e3b0c442-98fc-11ee-b9d1-0242ac120002",
      "usuario_id": "8f3b1234-11ee-b9d1-0242ac120002",
      "modulo": "inventario",
      "accion": "crear_producto",
      "entidad": "Producto",
      "entidad_id": "a1b2c3d4-11ee-b9d1-0242ac120002",
      "detalle": {
        "sku": "PROD-100",
        "nombre": "Refresco 600ml"
      },
      "ip_address": null,
      "fecha": "2026-09-21T17:30:00Z",
      "usuario": {
        "id": "8f3b1234-11ee-b9d1-0242ac120002",
        "nombre": "Carlos Gerente",
        "email": "carlos@pos.local"
      }
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

---

### 2. Obtener un Log de Auditoría por ID

```
GET /api/v1/auditoria/{log_id}?include=usuario
```

Devuelve el detalle individual del log o `404 Not Found` si el ID no existe.

---

## 🛠️ Cómo agregar auditoría en un módulo nuevo

Si agregas un nuevo módulo o endpoint al backend y deseas registrar su auditoría:

### Paso 1: Publicar el evento en el Router o Use Case
En la función del router (después de ejecutar el caso de uso con éxito), importa `event_bus` de `app.shared.events`:

```python
from app.shared.events import event_bus

@router.post("/mi-modulo")
async def crear_algo(
    body: CrearAlgoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("mi_modulo.crear")),
):
    resultado = await CrearAlgoUseCase(...).ejecutar(...)
    
    await event_bus.publicar("MiEntidadCreada", {
        "usuario_id": actual.id,
        "modulo": "mi_modulo",
        "accion": "crear_mi_entidad",
        "entidad": "MiEntidad",
        "entidad_id": str(resultado.id),
        "detalle": {"nombre": resultado.nombre},
    }, db)
    
    return ok(resultado)
```

### Paso 2: Suscribir el evento en listeners
En `app/modules/auditoria/infrastructure/listeners.py`, agrega la suscripción:

```python
event_bus.suscribir("MiEntidadCreada", registrar_auditoria)
```

¡Listo! Con esto, el evento se guardará automáticamente en `log_auditoria` en la misma transacción.

---

## 🔐 Permisos y Seguridad

| Permiso | Uso | Roles por Defecto |
|---|---|---|
| `auditoria.leer` | Consultar la lista y detalle de logs de auditoría | Admin, Gerente |

---

## ⚠️ Códigos de Error Comunes

| Código | Error | Causa |
|---|---|---|
| `401` | Unauthorized | Token JWT faltante o expirado. |
| `403` | Forbidden | El usuario no cuenta con el permiso `auditoria.leer`. |
| `404` | Not Found | El `log_id` especificado no existe. |
| `422` | Unprocessable Content | Parámetro `sort` inválido. Los campos permitidos son `fecha`, `created_at`, `modulo`, `accion`. |
