
from os import getenv, path as os_path

from dotenv import load_dotenv
from pydantic.v1 import BaseSettings


load_dotenv(dotenv_path=os_path.join(os_path.dirname(__file__), "..", "..", "..", ".env"))


class Settings(BaseSettings):

    ASYNC_DATABASE_URL: str = getenv("ASYNC_DATABASE_URL")
    DATABASE_URL: str = getenv("DATABASE_URL")

settings = Settings()