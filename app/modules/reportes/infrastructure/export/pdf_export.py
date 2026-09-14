"""ponytail: tabla simple con ancho de columna parejo (sin auto-ajuste por
contenido). Alcanza para reportes de pocas columnas; si hace falta texto
largo/columnas dispares, pasar a fpdf2 con anchos por columna calculados."""
from fpdf import FPDF


def render_pdf(titulo: str, headers: list[str], rows: list[list]) -> bytes:
    pdf = FPDF(orientation="L" if len(headers) > 5 else "P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    ancho_col = (pdf.w - 2 * pdf.l_margin) / max(len(headers), 1)

    pdf.set_font("Helvetica", "B", 9)
    for h in headers:
        pdf.cell(ancho_col, 8, str(h), border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for fila in rows:
        for valor in fila:
            pdf.cell(ancho_col, 7, str(valor), border=1)
        pdf.ln()

    return bytes(pdf.output())
