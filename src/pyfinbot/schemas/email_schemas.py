
from pydantic import BaseModel


class EmailSyncSummary(BaseModel):
    total_emails: int
    created: int
    skipped: int
    errors: list[str]
