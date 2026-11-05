
from pydantic import BaseModel


class DividendSyncResult(BaseModel):
    created: list[str]
    updated: list[str]
    errors: list[str]
