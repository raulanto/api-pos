# Guía: Sistema de Señales Reactivas en Tiempo Real (WebSockets)

> Cómo funciona la arquitectura Pub/Sub en tiempo real de la API backend mediante WebSockets,
> la estructura de los mensajes transmitidos por canal/módulo, la sanitización de datos y 
> la forma de conectar y consumir endpoints WebSockets.
> Todo cuelga del endpoint `/api/v1/signals/ws/{modulo}`.

---

## ⚡ La idea en dos minutos

- **Patrón Publish/Subscribe Desacoplado**: Cuando ocurre una acción en cualquier UseCase (ej. crear cita, venta, pedido, movimiento de caja), la aplicación emite un evento de dominio in-process mediante `event_bus.publicar()`.
- **Retransmisión Automática**: El listener global de señales escucha los eventos transmitidos en `event_bus` y los retransmite en tiempo real a todos los clientes WebSocket suscritos al canal correspondiente.
- **Canales por Módulo**: Las conexiones se aíslan por módulo (`agenda`, `ventas`, `caja`, `inventario`, `usuarios`, `clientes`, `proveedores`, `promociones`, `sucursales`, `pedidos`).
- **Autenticación Vía Token Query**: Cada conexión WebSocket valida opcionalmente el token JWT pasado como parámetro query (`?token=<JWT>`).
- **Sanitización de Datos Sensibles**: Antes de transmitir una señal a través del WebSocket, los campos sensibles (tales como `password`, `token`, `secret`, `pin`, `cvv`, etc.) se filtran y enmascaran a `"********"`.

---

## 🏗️ Arquitectura General del Backend

```
 ┌─────────────────────────────────────────────────────────────┐
 │                       Backend FastAPI                       │
 └─────────────────────────────────────────────────────────────┘
  Acción en UseCase (ej. Crear Cita, Venta, Pedido, Producto)
                              │
                              ▼
  `await event_bus.publicar("CitaCreada", payload, db)`
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
   [ Listener Auditoría ]          [ Listener Señales ]
   (Persiste en BD dentro          (Sanitiza payload)
    del mismo commit)                        │
                                             ▼
                                     `SignalManager`
                             (Gestión de conexiones WebSockets)
                                             │
 ┌───────────────────────────────────────────┴─────────────────┐
 │                      Canales WebSocket                      │
 └─────────────────────────────────────────────────────────────┘
  `ws://<host>:<puerto>/api/v1/signals/ws/{modulo}?token=<JWT>`
```

---

## 📡 Contrato de la API de Señales (WebSocket)

- **URL base:** `ws://<host>:<puerto>/api/v1/signals/ws/{modulo}`
- **Parámetros Query:** `token` (opcional, Token JWT Bearer del usuario autenticado).
- **Módulos / Canales Soportados:** `agenda`, `ventas`, `caja`, `inventario`, `usuarios`, `clientes`, `proveedores`, `promociones`, `sucursales`, `pedidos`.

### Estructura del JSON Transmitido (Payload)

```json
{
  "modulo": "agenda",
  "evento": "CitaCreada",
  "data": {
    "usuario_id": "8f3b1234-11ee-b9d1-0242ac120002",
    "modulo": "agenda",
    "accion": "CitaCreada",
    "entidad": "Cita",
    "entidad_id": "a1b2c3d4-11ee-b9d1-0242ac120002",
    "detalle": {
      "paciente": "María López",
      "fecha_hora": "2026-09-22T10:00:00Z"
    },
    "ip_address": "127.0.0.1"
  }
}
```

> **Nota de Seguridad**: Si `detalle` contiene claves como `password` o `refresh_token`, su valor será reemplazado automáticamente por `"********"`.

---

## 📡 Lista de Eventos Emitidos por Módulo

El backend transmite automáticamente las siguientes señales en tiempo real al registrarse acciones en el sistema:

### 📅 Agenda
- `CitaCreada`: Cita agendada.
- `CitaAsignada`: Empleado asignado a la cita.
- `CitaOfertaAceptada`: Oferta de cita aceptada por el empleado.
- `CitaOfertaRechazada`: Oferta rechazada.
- `CitaEstadoActualizado`: Cambio de estado de la cita (`en_proceso`, `completada`, etc.).
- `CitaCancelada`: Cancelación de cita.
- `CitaReagendada`: Cambio de horario/fecha de cita.

### 🛒 Ventas
- `VentaCreada`: Nueva venta cobrada en caja.
- `VentaAnulada`: Venta cancelada o anulada.
- `DescuentoManualAplicado`: Descuento especial aplicado en venta.

### 💰 Caja
- `CajaTurnoAbierto`: Apertura de turno/cajón con saldo inicial.
- `CajaTurnoCerrado`: Arqueo y cierre de turno.
- `MovimientoCajaRegistrado`: Entrada, salida o retiro de efectivo.
- `TurnoConciliado`: Conciliación gerencial de turno.

### 📦 Inventario
- `ProductoCreado`: Alta de producto en catálogo.
- `ProductoEditado`: Edición de información de producto.
- `ProductoDesactivado`: Baja lógica de producto.
- `CategoriaCreada`: Creación de categoría.
- `CategoriaEditada`: Edición de categoría.
- `MovimientoInventarioRegistrado`: Entrada/salida/ajuste de stock.
- `TransferenciaInventarioRegistrada`: Traspaso de mercancía entre sucursales.

### 📋 Pedidos
- `PedidoCreado`: Registro de nuevo pedido.
- `PedidoConfirmado`: Confirmación de pedido.
- `PedidoCancelado`: Cancelación de pedido.
- `PedidoReabierto`: Reapertura de pedido.
- `PedidoEntregaActualizada`: Cambio en estado de entrega o repartidor.
- `PedidoAnticipoRegistrado`: Registro de anticipo o pago parcial.
- `PedidoServiciosAsignados`: Asignación de personal a servicios del pedido.
- `PedidoFacturado`: Facturación del pedido a venta.

---

## 💻 Ejemplos de Conexión y Pruebas

### Pruebas Automatizadas en Backend
Para verificar el funcionamiento del gestor de señales y los endpoints WebSockets del backend:

```bash
uv run pytest tests/core/test_signals.py
```

### Ejemplo de Cliente genérico en JavaScript / WebSockets

```javascript
const modulo = 'agenda';
const token = localStorage.getItem('access_token');
const wsUrl = `ws://localhost:8000/api/v1/signals/ws/${modulo}?token=${encodeURIComponent(token)}`;

const socket = new WebSocket(wsUrl);

socket.onopen = () => {
  console.log(`Conectado al canal WebSocket de [${modulo}]`);
};

socket.onmessage = (event) => {
  const signal = JSON.parse(event.data);
  console.log('Señal recibida en tiempo real:', signal.evento, signal.data);
};

socket.onerror = (error) => {
  console.error('Error WebSocket:', error);
};

socket.onclose = () => {
  console.log('Conexión WebSocket cerrada');
};
```
