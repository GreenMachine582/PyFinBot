
from os import path as os_path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


load_dotenv(dotenv_path=os_path.join(os_path.dirname(__file__), "..", "..", "..", ".env"))


class Settings(BaseSettings):
    ASYNC_DATABASE_URL: str = ""
    DATABASE_URL: str = ""
    DB_ECHO: bool = False

settings = Settings()