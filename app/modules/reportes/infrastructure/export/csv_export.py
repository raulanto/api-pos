import csv
from io import StringIO


def render_csv(headers: list[str], rows: list[list]) -> bytes:
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    # BOM: Excel abre acentos bien al doble-clickear el .csv en Windows.
    return buf.getvalue().encode("utf-8-sig")
