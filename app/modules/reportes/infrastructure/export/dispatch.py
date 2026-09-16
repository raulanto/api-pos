from app.modules.reportes.infrastructure.export.csv_export import render_csv
from app.modules.reportes.infrastructure.export.excel_export import render_excel
from app.modules.reportes.infrastructure.export.pdf_export import render_pdf

EXTENSION = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}
MEDIA_TYPE = {
    "csv": "text/csv; charset=utf-8",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def render(formato: str, titulo: str, headers: list[str], rows: list[list]) -> bytes:
    if formato == "excel":
        return render_excel(headers, rows, titulo)
    if formato == "pdf":
        return render_pdf(titulo, headers, rows)
    return render_csv(headers, rows)
