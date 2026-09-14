from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font


def render_excel(headers: list[str], rows: list[list], titulo: str = "Reporte") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]  # límite de Excel para nombres de hoja

    ws.append(headers)
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for fila in rows:
        ws.append(fila)

    for columna in ws.columns:
        largo = max((len(str(c.value)) for c in columna if c.value is not None), default=10)
        ws.column_dimensions[columna[0].column_letter].width = min(largo + 2, 40)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
