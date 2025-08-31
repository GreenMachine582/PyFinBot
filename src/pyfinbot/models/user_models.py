from typing import Optional, List
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[str] = Field(primary_key=True, index=True, description="External ID of the user")
    active: bool = Field(default=True, description="User active status")

    create_datetime: datetime = Field(default_factory=datetime.now)
    write_datetime: datetime = Field(default_factory=datetime.now)

    transactions: List["Transaction"] = Relationship(
        back_populates="user",
        cascade_delete=True
    )
