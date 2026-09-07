"""Renderiza un `TicketData` a un PDF de ticket (ancho ~80 mm).

ponytail: PDF rasterizado con Pillow (una imagen envuelta en PDF, a 203 dpi como
una impresora térmica). Para el uso pedido —mostrarlo / imprimirlo en la app—
alcanza y no suma dependencias. Si hace falta texto seleccionable o PDF más
liviano, cambiar por `fpdf2` (una dependencia, pura Python).
"""
from decimal import Decimal
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from app.modules.ventas.application.use_cases.generar_ticket import TicketData

_W = 576            # 80 mm a 203 dpi
_PAD = 18
_DPI = 203.0
_F = ImageFont.load_default(size=20)
_FB = ImageFont.load_default(size=26)
_FS = ImageFont.load_default(size=16)
_LH = 26           # alto de línea


def _money(v: Decimal) -> str:
    return f"{v:,.2f}"


def _qty(v: Decimal) -> str:
    return format(v.normalize(), "f")   # 1.0000 -> "1" ; 2.5000 -> "2.5"


def render_ticket_pdf(data: TicketData) -> bytes:
    # Pasada 1: juntar las filas (texto izq, texto der, fuente) y medir el alto.
    filas: list[tuple[str, str, ImageFont.FreeTypeFont]] = []

    def sep():
        filas.append(("-" * 46, "", _FS))

    filas.append((data.sucursal_nombre, "", _FB))
    if data.sucursal_direccion:
        filas.append((data.sucursal_direccion, "", _FS))
    if data.sucursal_telefono:
        filas.append((f"Tel: {data.sucursal_telefono}", "", _FS))
    sep()
    filas.append((f"Ticket #{data.folio}", data.fecha.strftime("%d/%m/%Y %H:%M"), _FS))
    filas.append((f"Estado: {data.estado}", "", _FS))
    if data.cliente_nombre:
        filas.append((f"Cliente: {data.cliente_nombre}", "", _FS))
    sep()

    for l in data.lineas:
        filas.append((l.nombre[:40], "", _F))
        detalle = f"  {_qty(l.cantidad)} x {_money(l.precio_unitario)}"
        filas.append((detalle, _money(l.importe), _F))
        if l.descuento > 0:
            etq = f"  desc {l.promo_etiqueta}" if l.promo_etiqueta else "  descuento"
            filas.append((etq, f"-{_money(l.descuento)}", _FS))
    sep()

    filas.append(("Subtotal", _money(data.subtotal), _F))
    if data.total_promociones > 0:
        filas.append(("Promociones", f"-{_money(data.total_promociones)}", _F))
    if data.descuento_total > 0:
        filas.append(("Descuento", f"-{_money(data.descuento_total)}", _F))
    filas.append(("TOTAL", _money(data.total), _FB))
    sep()

    for p in data.pagos:
        filas.append((f"Pago {p.metodo}", _money(p.monto), _F))
        if p.monto_recibido is not None:
            filas.append(("  Recibido", _money(p.monto_recibido), _FS))
            filas.append(("  Cambio", _money(p.cambio), _FS))
    if data.saldo_pendiente > 0:
        filas.append(("Saldo pendiente", _money(data.saldo_pendiente), _F))
    if data.total_devuelto > 0:
        filas.append(("Devuelto", _money(data.total_devuelto), _F))

    sep()
    filas.append(("Gracias por su compra", "", _FS))

    alto = _PAD * 2 + _LH * len(filas)
    img = Image.new("RGB", (_W, alto), "white")
    d = ImageDraw.Draw(img)
    y = _PAD
    for izq, der, font in filas:
        d.text((_PAD, y), izq, font=font, fill="black")
        if der:
            w = d.textlength(der, font=font)
            d.text((_W - _PAD - w, y), der, font=font, fill="black")
        y += _LH

    buf = BytesIO()
    img.save(buf, format="PDF", resolution=_DPI)
    return buf.getvalue()
