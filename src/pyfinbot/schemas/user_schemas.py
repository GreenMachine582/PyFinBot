from datetime import datetime
from pydantic import BaseModel


class UserBase(BaseModel):
    external_id: int
    active: bool
    create_datetime: datetime
    write_datetime: datetime


class UserCreate(BaseModel):
    external_id: int
