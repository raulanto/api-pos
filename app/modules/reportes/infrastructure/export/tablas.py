"""Convierte la salida de cada método de `ReporteQueryPort` a (headers, rows)
para exportar (CSV/Excel/PDF). Un solo punto de verdad: lo usan tanto los
endpoints (export bajo demanda) como el task de reportes programados."""


def tabla_ventas(res) -> tuple[list[str], list[list]]:
    rows = [[str(d.dia), d.numero_ventas, str(d.total)] for d in res.por_dia]
    rows.append(["TOTAL", res.numero_ventas, str(res.total_vendido)])
    return ["dia", "numero_ventas", "total"], rows


def tabla_ventas_por_metodo_pago(res) -> tuple[list[str], list[list]]:
    rows = [[m.metodo_pago, str(m.total)] for m in res.detalle]
    rows.append(["TOTAL", str(res.total_general)])
    return ["metodo_pago", "total"], rows


def tabla_inventario_valorizado(res) -> tuple[list[str], list[list]]:
    rows = [[c.nombre, str(c.valor), c.numero_productos] for c in res.por_categoria]
    rows.append(["TOTAL", str(res.valor_total), ""])
    return ["categoria", "valor", "numero_productos"], rows


def tabla_mermas_ajustes(res) -> tuple[list[str], list[list]]:
    rows = [
        [d.tipo, d.numero_movimientos, str(d.cantidad_total), str(d.valor_estimado)]
        for d in res.detalle
    ]
    return ["tipo", "numero_movimientos", "cantidad_total", "valor_estimado"], rows


def tabla_clientes_con_saldo(items) -> tuple[list[str], list[list]]:
    rows = [[i.nombre, str(i.saldo_credito), str(i.limite_credito)] for i in items]
    return ["nombre", "saldo_credito", "limite_credito"], rows
