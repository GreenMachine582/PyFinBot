from datetime import datetime

from greentechhub_core.users import UserAccount
from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """A user account as the API shows it (never its password hash)."""

    id: str
    username: str
    email: str | None
    email_verified: bool
    display_name: str | None
    active: bool
    auth_source: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


def user_out(account: UserAccount) -> UserBase:
    return UserBase(**{name: getattr(account, name) for name in UserBase.model_fields})


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=72)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    active: bool | None = None
    password: str | None = Field(default=None, min_length=1, max_length=72)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=255)
