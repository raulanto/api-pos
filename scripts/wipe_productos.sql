-- Vacía TODO lo relacionado con productos y su stock. Esquema intacto.
--
-- OJO: por las FK, esto también borra VENTAS y CAJA (detalle_venta apunta a
-- producto). Es un reset de datos de desarrollo, no una operación de producción.
-- Se conservan: categoria, unidad_medida, sucursal, usuario, roles/permisos,
-- log_auditoria (append-only, no tiene FK a estas tablas).
--
-- Uso:
--   docker compose exec -T db psql -U postgres -d pos_db -f - < scripts/wipe_productos.sql
--   (o, corriendo fuera de docker)  psql "$DATABASE_URL" -f scripts/wipe_productos.sql

BEGIN;

TRUNCATE
    pago,
    detalle_venta,
    venta,
    caja_turno,
    movimiento_inventario,
    instancia_abierta,
    existencia_lote,
    lote,
    existencia,
    producto_imagen,
    producto_componente,
    producto_unidad,
    producto
RESTART IDENTITY CASCADE;

COMMIT;

-- Para vaciar también el catálogo de categorías, agregá `categoria` a la lista
-- (arriba de `producto`). `unidad_medida` viene sembrada por migración: si la
-- vaciás, restaurala con `alembic downgrade` + `upgrade` de esa revisión.
