from __future__ import annotations

from contextlib import asynccontextmanager

import importlib
import pkgutil

from fastapi import FastAPI
from fastapi_pagination import add_pagination

from . import version, api
from .db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to initialize the database on startup.
    """
    await init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title=version.PROJECT_NAME_TEXT,
    description=version.DESCRIPTION,
    version=version.VERSION
)
# Register all routers

# Loop through all modules in the routes package
for _, module_name, _ in pkgutil.iter_modules(api.__path__):
    module = importlib.import_module(f"{api.__name__}.{module_name}")
    if hasattr(module, "router"):
        app.include_router(module.router, prefix="/api")


# Enable pagination for all routes
add_pagination(app)
