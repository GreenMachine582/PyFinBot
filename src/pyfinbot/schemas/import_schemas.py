from pydantic import BaseModel


class ImportRowError(BaseModel):
    row: int  # spreadsheet row number (the header is row 1)
    message: str


class ImportSummary(BaseModel):
    total_rows: int
    created: int
    skipped: int
    errors: list[str]  # "Row N: message" — row_errors, flattened
    row_errors: list[ImportRowError] = []
