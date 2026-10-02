# Guía Detallada: Sistema de Señales en Tiempo Real vía WebSockets

> Documentación oficial de la arquitectura, contrato de conexión, parámetros,
> sanitización de datos y funcionamiento del servidor WebSocket en el POS Backend FastAPI.
> Endpoint base: `ws://<host>:<puerto>/api/v1/signals/ws/{modulo}`

---

## 📐 1. Arquitectura del Sistema de Señales

El sistema utiliza un patrón **Publish/Subscribe desacoplado** integrado directamente con el bus de eventos in-process (`event_bus`) de la aplicación.

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

## 🛠️ 2. Especificación de Endpoints y Parámetros

### Endpoint Único de Conexión

```http
GET /api/v1/signals/ws/{modulo}?token={jwt_token}
Upgrade: websocket
Connection: Upgrade
```

| Parámetro | Ubicación | Tipo | Requerido | Descripción |
|---|---|---|---|---|
| `modulo` | **Path** | `string` | **Sí** | Identificador del canal/módulo al que se suscribe el cliente. |
| `token` | **Query** | `string` | No (Opcional) | Token JWT Bearer de acceso. Si se proporciona y es inválido o expiró, el servidor rechaza la conexión con código `1008 (Policy Violation)`. |

---

## 📺 3. Canales / Módulos Disponibles

Los clientes pueden suscribirse a cualquiera de los siguientes canales:

- **`agenda`**: Citas agendadas, asignadas, reagendadas, canceladas o cambios de estado.
- **`ventas`**: Registro de ventas cobradas, cobros o anulaciones de tickets.
- **`caja`**: Apertura/cierre de turnos de caja y movimientos de cajón.
- **`inventario`**: Altas, ediciones, ajustes o movimientos de stock y transferencias entre sucursales.
- **`pedidos`**: Cambios de estado en pedidos, anticipos, entregas o facturación.
- **`usuarios`**: Alta, modificación o desactivación de cuentas.
- **`clientes`**: Registro o edición de clientes.
- **`proveedores`**: Recepciones o devoluciones de proveedores.
- **`promociones`**: Modificaciones o activación de promociones.
- **`sucursales`**: Cambios en configuración de sucursales.

---

## 🔒 4. Autenticación y Seguridad

1. **Validación JWT**: Si el cliente envía el parámetro `?token=<JWT>`, el servidor verifica la firma y la fecha de expiración mediante `decode_access_token()`. Si el token es inválido, el socket se cierra de inmediato con el código de estado WebSocket `1008 Policy Violation`.
2. **Sanitización de Datos Sensibles**: Antes de enviar cualquier mensaje JSON al WebSocket, el `SignalManager` ejecuta un filtro que enmascara automáticamente valores de claves sensibles (tales como `password`, `token`, `secret`, `pin`, `cvv`, `card_number`, etc.) a `"********"`.

---

## 📦 5. Formato del Mensaje Transmitido (Payload)

Cada mensaje enviado por el servidor a los clientes conectados sigue este esquema estándar JSON:

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
      "servicio_nombre": "Corte de Cabello",
      "cliente_nombre": "María López",
      "fecha_hora": "2026-09-22T10:00:00Z"
    },
    "ip_address": "127.0.0.1"
  }
}
```

---

## 🔄 6. Ciclo de Vida de la Conexión (`SignalManager`)

- **Conexión (`conectar`)**: El servidor acepta el handshake del cliente y registra el socket en la lista interna de conexiones activas asociadas a ese `modulo`.
- **Mantenimiento**: El servidor mantiene un bucle pasivo escuchando la conexión (`websocket.receive_text()`) para recibir mensajes de Keep-Alive (Heartbeat/Ping) enviadas por el cliente.
- **Emisión (`emitir_modulo`)**: Cuando ocurre un evento en el backend, el listener toma el mensaje, lo sanitiza y lo transmite en paralelo a todos los sockets activos del canal.
- **Desconexión (`desconectar`)**: Si un socket se cierra (desconexión limpia del cliente o pérdida de red), el `SignalManager` captura la excepción `WebSocketDisconnect` y remueve la conexión de la lista para evitar fugas de memoria.

---

## 🧪 7. Pruebas y Verificación

### Correr Pruebas Automatizadas del Backend
```bash
uv run pytest tests/core/test_signals.py
```

### Ejemplo de Cliente en JavaScript Nativo

```javascript
const modulo = 'agenda';
const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
const url = `ws://localhost:8000/api/v1/signals/ws/${modulo}?token=${encodeURIComponent(token)}`;

const socket = new WebSocket(url);

socket.onopen = () => {
  console.log(`Conectado exitosamente al canal [${modulo}]`);
};

socket.onmessage = (event) => {
  const signal = JSON.parse(event.data);
  console.log('Señal en tiempo real recibida:', signal.evento, signal.data);
};

socket.onerror = (error) => {
  console.error('Error en WebSocket:', error);
};

socket.onclose = (event) => {
  console.log(`Conexión cerrada. Código: ${event.code}`);
};
```
