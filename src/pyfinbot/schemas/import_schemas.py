from pydantic import BaseModel


class ImportSummary(BaseModel):
    total_rows: int
    created: int
    skipped: int
    errors: list[str]
