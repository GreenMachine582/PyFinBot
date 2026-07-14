from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserBase(BaseModel):
    id: str
    active: bool
    create_datetime: datetime
    write_datetime: datetime


class UserCreate(BaseModel):
    id: str


class UserUpdate(BaseModel):
    active: Optional[bool] = None
