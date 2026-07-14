
import os
import secrets
import warnings
from os import path as os_path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


load_dotenv(dotenv_path=os_path.join(os_path.dirname(__file__), "..", "..", "..", ".env"))


class Settings(BaseSettings):
    ASYNC_DATABASE_URL: str = ""
    DATABASE_URL: str = ""
    DB_ECHO: bool = False

    # JWT signing secret. Defaults to a fresh random value each process start
    # (so tokens issued before a restart become invalid) unless overridden via
    # the environment/.env — set this explicitly in any persistent deployment.
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

settings = Settings()

if not settings.SECRET_KEY:
    settings.SECRET_KEY = secrets.token_hex(32)
    if not os.environ.get("SECRET_KEY"):
        warnings.warn(
            "SECRET_KEY is not set in the environment/.env — using a random "
            "ephemeral key for this process. All issued tokens will become "
            "invalid on restart. Set SECRET_KEY explicitly for any deployment "
            "that needs to survive a restart.",
            stacklevel=2,
        )
