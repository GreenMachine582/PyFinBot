from typing import List

from pydantic import BaseModel


class DividendSyncResult(BaseModel):
    created: List[str]
    updated: List[str]
    errors: List[str]
