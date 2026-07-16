from typing import List

from pydantic import BaseModel


class EmailSyncSummary(BaseModel):
    total_emails: int
    created: int
    skipped: int
    errors: List[str]
