from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    # only for type checkers; avoids runtime import cycles
    from .transaction_models import Transaction


class User(SQLModel, table=True):
    id: Optional[str] = Field(primary_key=True, index=True, description="External ID of the user")
    active: bool = Field(default=True, description="User active status")
    password_hash: Optional[str] = Field(default=None, description="Bcrypt hash of the user's password")

    create_datetime: datetime = Field(default_factory=datetime.now)
    write_datetime: datetime = Field(default_factory=datetime.now)

    transactions: List["Transaction"] = Relationship(
        back_populates="user",
        cascade_delete=True
    )
