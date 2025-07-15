from typing import Optional
from datetime import datetime

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, description="External ID of the user")
    active: bool = Field(default=True, description="User active status")

    create_datetime: datetime = Field(default_factory=datetime.now)
    write_datetime: datetime = Field(default_factory=datetime.now)
