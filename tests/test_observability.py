"""Logging, health and error responses (greentechhub v0.12 adoption, item
6): /api errors are greentechhub's {code, message, details} envelope with
the same statuses as before, pages keep their redirects and HTML errors,
/health and /health/ready, and JSON logs tagged with the service."""
import json
import logging

from greentechhub_core.health import HealthResult

from pyfinbot.db import session as session_module

from .conftest import create_stock, make_admin, register_and_login, web_login

HX = {"HX-Request": "true"}


def _envelope(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"code", "message", "details"}, body
    assert body["code"] == code, body
    return body


# /api: the envelope


async def test_api_not_found_and_bad_requests(client):
    _envelope(await client.get("/api/stocks/999"), 404, "not_found")
    _envelope(await client.get("/api/stocks/", params={"filters": "{not json"}), 400, "invalid_filters")
    await create_stock(client, "DUP")
    dup = await client.post("/api/stocks/", json={"symbol": "DUP", "market": "ASX", "name": "Dup"})
    assert _envelope(dup, 400, "stock_exists")["message"] == "Stock already registered"


async def test_api_auth_errors_keep_the_bearer_challenge(client):
    no_token = await client.get("/api/users/")
    _envelope(no_token, 401, "unauthorized")
    assert no_token.headers["WWW-Authenticate"] == "Bearer"

    bad_token = await client.get("/api/users/", headers={"Authorization": "Bearer nope"})
    assert _envelope(bad_token, 401, "unauthorized")["message"] == "Could not validate credentials"
    assert bad_token.headers["WWW-Authenticate"] == "Bearer"

    wrong_password = await client.post("/api/auth/login", data={"username": "nobody", "password": "x"})
    _envelope(wrong_password, 401, "unauthorized")

    plain = await register_and_login(client, "obs-plain")
    _envelope(await client.get("/api/users/", headers=plain), 403, "forbidden")
    _envelope(await client.get("/api/users/someone-else", headers=plain), 403, "forbidden")


async def test_api_validation_and_routing_errors(client):
    admin = await register_and_login(client, "obs-admin")
    await make_admin(client, "obs-admin")
    invalid = await client.post("/api/users/", json={"id": "no-password"}, headers=admin)
    body = _envelope(invalid, 422, "validation_error")
    assert isinstance(body["details"], list) and body["details"][0]["loc"][-1] == "password"

    _envelope(await client.get("/api/no-such-route"), 404, "not_found")
    _envelope(await client.delete("/api/users/", headers=admin), 405, "method_not_allowed")


# pages: unchanged


async def test_pages_keep_their_redirects_and_errors(client):
    page = await client.get("/transactions", follow_redirects=False)
    assert page.status_code == 303 and page.headers["location"] == "/login"
    hx = await client.get("/transactions", headers=HX, follow_redirects=False)
    assert hx.status_code == 401 and hx.headers["HX-Redirect"] == "/login"
    assert "code" not in hx.text

    await web_login(client, "obs-pages")
    missing = await client.get("/stocks/999/edit", headers=HX)
    assert missing.status_code == 404 and "code" not in missing.json()  # FastAPI's {"detail": ...}
    roles = await client.get("/admin/roles", headers={"Accept": "text/html"})
    assert roles.status_code == 403 and "message" not in roles.text


# health


async def test_health_and_readiness(client):
    live = await client.get("/health")
    assert live.status_code == 200 and live.json() == {"status": "healthy"}
    ready = await client.get("/health/ready")
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "healthy"


async def test_readiness_fails_when_the_database_check_does(client, monkeypatch):
    async def down(engine):
        return HealthResult.unhealthy("database", "connection refused")

    monkeypatch.setattr(session_module, "check_database", down)
    ready = await client.get("/health/ready")
    assert ready.status_code == 503 and ready.json()["status"] != "healthy"


# logging


def test_logs_are_json_tagged_with_the_service():
    import pyfinbot.pyfinbot  # noqa: F401  # configures logging at import

    from greentechhub_core.logging import JSONFormatter

    # pytest adds its own capture handlers to the root logger; find core's.
    formatters = [h.formatter for h in logging.getLogger().handlers if isinstance(h.formatter, JSONFormatter)]
    assert formatters, "no JSON log handler on the root logger"
    record = logging.LogRecord("pyfinbot.test", logging.WARNING, __file__, 1, "hello %s", ("logs",), None)
    line = json.loads(formatters[0].format(record))
    assert line["message"] == "hello logs" and line["service"] == "pyfinbot"
    assert line["level"] == "WARNING"


def test_startup_migrations_keep_the_json_logging(tmp_path):
    # The app migrates on startup (db.session._run_migrations); alembic's env.py
    # must not swap the root handlers for alembic.ini's plain ones. A subprocess:
    # the alembic env imports the models as src.pyfinbot.
    import os
    import subprocess
    import sys
    from pathlib import Path

    db = tmp_path / "logging.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "ASYNC_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    script = (
        "import logging, sys; sys.path.insert(0, '.')\n"
        "from greentechhub_core.logging import JSONFormatter, configure_logging\n"
        "configure_logging('INFO', service='pyfinbot')\n"
        "from src.pyfinbot.db.session import _run_migrations\n"
        "_run_migrations()\n"
        "print(any(isinstance(h.formatter, JSONFormatter) for h in logging.getLogger().handlers))\n"
    )
    out = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1], env=env,
                         check=True, capture_output=True, text=True)
    assert out.stdout.strip().splitlines()[-1] == "True"


def test_uvicorn_logs_go_through_the_json_root():
    import pyfinbot.pyfinbot  # noqa: F401

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        assert log.propagate and not log.handlers, name
