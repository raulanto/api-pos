# Guía Completa: Sistema de Notificaciones Persistentes y Tiempo Real (WebSockets)

> **Documentación Oficial de Integración**
> Arquitectura, Protocolos de Conexión, Endpoints REST, Esquemas de Respuesta y Guía de Conexión en Tiempo Real vía WebSockets.
> 
> **Endpoints Base:**
> - API REST: `http://<host>:<puerto>/api/v1/notificaciones`
> - WebSockets: `ws://<host>:<puerto>/api/v1/signals/ws/{modulo}?token=<JWT_TOKEN>`

---

## 📐 1. Arquitectura del Sistema

El sistema de notificaciones combina dos estrategias desacopladas para garantizar persistencia e inmediatez visual:

```
  ┌─────────────────────────────────────────────────────────────┐
  │                      Acción de Negocio                      │
  │     (Ej. Crear Cita, Asignar Cita, Cambiar Estado, etc.)     │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                   await event_bus.publicar(...)
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│     Notificaciones (DB)       │               │      WebSockets (Signals)     │
│  Guarda registro persistente  │               │ Transmite en tiempo real      │
│  en PostgreSQL (notificacion) │               │ por módulo (agenda,           │
│                               │               │  notificaciones, etc.)        │
└──────────────┬────────────────┘               └──────────────┬────────────────┘
               │                                               │
      API REST GET /notificaciones                     WebSocket Client
      (Paginación, Filtros, Unread)                    (Angular / React / Mobile)
```

1. **Pub/Sub in-process (`event_bus`):** Cuando ocurre un evento de dominio, el use case o endpoint emite un evento (`CitaCreada`, `CitaAsignada`, etc.).
2. **Persistencia (Base de Datos):** El listener `procesar_evento_notificacion` crea filas en la tabla `notificacion` dirigidas a los usuarios destinatarios.
3. **Señales en Tiempo Real (WebSockets):** Simultáneamente, `signal_manager` retransmite la señal a las conexiones WebSocket abiertas.

---

## 🔌 2. Protocolo de Conexión en Tiempo Real (WebSockets)

Para mantener una conexión abierta y "pintar" la interfaz automáticamente en cuanto suceda un evento, el cliente debe conectarse al servidor WebSocket de señales.

### 🌐 Contrato de Conexión WebSocket

```http
ws://<host>:<puerto>/api/v1/signals/ws/{modulo}?token=<JWT_TOKEN>
```

#### Parámetros de Conexión:

| Parámetro | Tipo | Ubicación | Requerido | Descripción |
| :--- | :--- | :--- | :--- | :--- |
| `modulo` | `string` | Path variable | **Sí** | Nombre del módulo a escuchar (`notificaciones`, `agenda`, `ventas`, `inventario`, etc.). |
| `token` | `string` | Query parameter | **Sí** (en prod) | JWT de autenticación obtenido en `POST /api/v1/usuarios/login`. |

---

### 📦 Estructura del Payload WebSocket Recibido

Cada mensaje transmitido por el WebSocket sigue un estándar de envoltura JSON:

```json
{
  "modulo": "notificaciones",
  "evento": "NuevaNotificacion",
  "data": {
    "id": "c7a8b9d0-1234-5678-90ab-cdef12345678",
    "usuario_id": "e8f9a0b1-2345-6789-01ab-cdef23456789",
    "modulo": "agenda",
    "tipo": "oferta_cita",
    "titulo": "Nueva oferta de cita disponible",
    "mensaje": "Se te ha ofertado una cita para Corte de Cabello (2026-09-22T18:00:00).",
    "leida": false,
    "created_at": "2026-09-22T17:25:00.123456Z",
    "datos": {
      "detalle": {
        "servicio_nombre": "Corte de Cabello",
        "fecha_hora": "2026-09-22T18:00:00"
      }
    }
  }
}
```

---

## 🗄️ 3. Modelo de Datos Persistente (`notificacion`)

En PostgreSQL, las notificaciones se almacenan en la tabla `notificacion`:

```sql
CREATE TABLE notificacion (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuario(id),
    sucursal_id UUID NULL REFERENCES sucursal(id),
    modulo VARCHAR(50) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    mensaje TEXT NOT NULL,
    leida BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_leida TIMESTAMPTZ NULL,
    entidad VARCHAR(100) NULL,
    entidad_id VARCHAR(100) NULL,
    datos JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 📡 4. Endpoints de la API REST (`/api/v1/notificaciones`)

Todos los endpoints requieren cabecera `Authorization: Bearer <JWT_TOKEN>`.

### 1️⃣ Listar Notificaciones Paginadas
Obtiene las notificaciones del usuario autenticado.

* **Método:** `GET`
* **URL:** `/api/v1/notificaciones`
* **Query Parameters:**
  - `leida` (`boolean`, opcional): `true` para leídas, `false` para no leídas. Omita para listar todas.
  - `modulo` (`string`, opcional): Filtrar por módulo (ej. `agenda`, `ventas`).
  - `page` (`int`, defecto `1`): Número de página.
  - `page_size` (`int`, defecto `20`, máx `100`): Registros por página.

* **Ejemplo de Respuesta (`200 OK`):**
```json
{
  "success": true,
  "data": [
    {
      "id": "c7a8b9d0-1234-5678-90ab-cdef12345678",
      "usuario_id": "e8f9a0b1-2345-6789-01ab-cdef23456789",
      "modulo": "agenda",
      "tipo": "oferta_cita",
      "titulo": "Nueva oferta de cita disponible",
      "mensaje": "Se te ha ofertado una cita para Corte de Cabello (2026-09-22T18:00:00).",
      "leida": false,
      "fecha_leida": null,
      "sucursal_id": "a1b2c3d4-...",
      "entidad": "Cita",
      "entidad_id": "f5e4d3c2-...",
      "datos": { "detalle": { ... } },
      "created_at": "2026-09-22T17:25:00Z"
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1,
      "has_next": false,
      "has_prev": false
    }
  }
}
```

---

### 2️⃣ Resumen de Notificaciones No Leídas
Retorna el contador rápido para pintar la insignia (badge) en la barra de navegación.

* **Método:** `GET`
* **URL:** `/api/v1/notificaciones/resumen`

* **Ejemplo de Respuesta (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "unread_count": 3
  }
}
```

---

### 3️⃣ Marcar Notificación como Leída
Cambia el estado de una notificación individual a `leida = true` y registra `fecha_leida`.

* **Método:** `PATCH`
* **URL:** `/api/v1/notificaciones/{id}/marcar-leida`

* **Ejemplo de Respuesta (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "id": "c7a8b9d0-1234-5678-90ab-cdef12345678",
    "leida": true,
    "fecha_leida": "2026-09-22T17:30:00Z"
  }
}
```

---

### 4️⃣ Marcar Todas como Leídas
Marca todas las notificaciones pendientes del usuario autenticado como leídas en una sola operación.

* **Método:** `PATCH`
* **URL:** `/api/v1/notificaciones/marcar-todas-leidas`

* **Ejemplo de Respuesta (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "message": "3 notificaciones marcadas como leídas",
    "count": 3
  }
}
```

---

## 💻 5. Guía de Implementación en Frontend (Angular / TypeScript)

A continuación se presenta un servicio listo para producción que gestiona la conexión WebSocket, la reconexión automática y el estado reactivo con RxJS:

```typescript
import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';

export interface Notificacion {
  id: string;
  usuario_id: string;
  modulo: string;
  tipo: string;
  titulo: string;
  mensaje: string;
  leida: boolean;
  created_at: string;
  datos?: any;
}

@Injectable({ providedIn: 'root' })
export class NotificacionesRealtimeService {
  private socket?: WebSocket;
  private wsUrl = 'ws://localhost:8000/api/v1/signals/ws/notificaciones';
  
  // Estado Reactivo
  public notificaciones$ = new BehaviorSubject<Notificacion[]>([]);
  public unreadCount = signal<number>(0);

  constructor(private http: HttpClient) {}

  /** Conecta al WebSocket en tiempo real */
  public conectarWebsocket(token: string): void {
    const urlConToken = `${this.wsUrl}?token=${encodeURIComponent(token)}`;
    this.socket = new WebSocket(urlConToken);

    this.socket.onopen = () => {
      console.log('✅ Conectado al canal WebSocket de Notificaciones');
    };

    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        
        // Reaccionar cuando llega una nueva notificación
        if (payload.evento === 'NuevaNotificacion' && payload.data) {
          this.procesarNotificacionEntrante(payload.data);
        }
      } catch (err) {
        console.error('Error parseando mensaje WebSocket:', err);
      }
    };

    this.socket.onclose = () => {
      console.warn('⚠️ WebSocket desconectado. Reintentando en 3s...');
      setTimeout(() => this.conectarWebsocket(token), 3000);
    };

    this.socket.onerror = (error) => {
      console.error('❌ Error en conexión WebSocket:', error);
      this.socket?.close();
    };
  }

  /** Procesa la llegada en tiempo real de una nueva notificación */
  private procesarNotificacionEntrante(nueva: Notificacion): void {
    // 1. Agregar al inicio de la lista reactiva
    const listaActual = this.notificaciones$.value;
    this.notificaciones$.next([nueva, ...listaActual]);

    // 2. Incrementar badge de no leídas
    this.unreadCount.update(count => count + 1);

    // 3. (Opcional) Reproducir sonido o mostrar Toast emergente
    this.mostrarToastNotificacion(nueva);
  }

  private mostrarToastNotificacion(notif: Notificacion): void {
    console.log(`🔔 TOAST: [${notif.titulo}] ${notif.mensaje}`);
  }

  /** Métodos API REST */
  public cargarIniciales(): void {
    this.http.get<any>('/api/v1/notificaciones?page=1&page_size=20').subscribe(res => {
      if (res.success) {
        this.notificaciones$.next(res.data);
      }
    });

    this.http.get<any>('/api/v1/notificaciones/resumen').subscribe(res => {
      if (res.success) {
        this.unreadCount.set(res.data.unread_count);
      }
    });
  }

  public marcarComoLeida(id: string): void {
    this.http.patch<any>(`/api/v1/notificaciones/${id}/marcar-leida`, {}).subscribe(res => {
      if (res.success) {
        // Actualizar estado local
        const lista = this.notificaciones$.value.map(n => 
          n.id === id ? { ...n, leida: true } : n
        );
        this.notificaciones$.next(lista);
        this.unreadCount.update(c => Math.max(0, c - 1));
      }
    });
  }
}
```

---

## 📌 Resumen de Mejores Prácticas

1. **Reconexión Automática:** El cliente debe tener un temporizador de reintento (`setTimeout` en el evento `onclose`) para restablecer la conexión si el servidor se reinicia o se pierde la red.
2. **Petición Inicial + WebSocket:** Al iniciar sesión o cargar la app, haz la llamada REST `GET /api/v1/notificaciones` y `GET /api/v1/notificaciones/resumen` para tener la foto inicial, y luego mantén abierto el WebSocket para recibir los incrementos delta en tiempo real.
3. **Heartbeat / Ping-Pong:** El socket mantiene automáticamente la conexión activa recibiendo pings del navegador.
