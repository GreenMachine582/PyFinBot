import csv
import io
from collections.abc import Iterable
from typing import Any

from fastapi.responses import Response

# A UTF-8 byte-order mark. Excel opens a CSV without one as Windows-1252, so
# UTF-8 text such as the FY label's en dash ("2025–26") shows up as "2025â€“26".
# With it, Excel, Numbers and LibreOffice all read UTF-8; pandas reads it with
# encoding="utf-8-sig".
BOM = chr(0xFEFF)  # U+FEFF, written as EF BB BF


def csv_download(rows: Iterable[Iterable[Any]], filename: str) -> Response:
    """`rows` (header first) as a UTF-8 CSV attachment named `filename`."""
    buf = io.StringIO()
    buf.write(BOM)
    csv.writer(buf).writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
    })
