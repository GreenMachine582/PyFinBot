from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    id: str
    active: bool
    create_datetime: datetime
    write_datetime: datetime


class UserCreate(BaseModel):
    id: str
    password: str = Field(max_length=72)


class UserUpdate(BaseModel):
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, max_length=72)
