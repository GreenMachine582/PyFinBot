"""The strict Content-Security-Policy (greentechhub-fastapi v0.17's register_csp):
every response carries greentechhub-ui's recommended policy with a fresh
nonce, every <script> the shell renders has that nonce, and frame-src takes
the Grafana origin when GRAFANA_ORIGIN is set."""

import re
from types import SimpleNamespace

from pyfinbot.pyfinbot import csp_frame_src

from .conftest import web_login

HTML = {"Accept": "text/html"}


def _nonce(header: str) -> str:
    return re.search(r"'nonce-([^']+)'", header).group(1)


async def test_pages_carry_the_policy_and_every_script_its_nonce(gth_client):
    await web_login(gth_client, "csp-user")
    page = await gth_client.get("/", headers=HTML)
    assert page.status_code == 200
    header = page.headers["Content-Security-Policy"]
    assert "script-src 'self' 'nonce-" in header and "object-src 'none'" in header
    assert "'unsafe-inline'" not in header.split("script-src")[1].split(";")[0]
    nonce = _nonce(header)
    scripts = re.findall(r"<script\b[^>]*>", page.text)
    assert scripts and all(f'nonce="{nonce}"' in tag for tag in scripts)


async def test_each_request_gets_a_fresh_nonce(gth_client):
    await web_login(gth_client, "csp-fresh")
    first = (await gth_client.get("/", headers=HTML)).headers["Content-Security-Policy"]
    second = (await gth_client.get("/", headers=HTML)).headers["Content-Security-Policy"]
    assert _nonce(first) != _nonce(second)


async def test_the_api_still_answers(gth_client):
    resp = await gth_client.get("/api/stocks/")
    assert resp.status_code == 200 and "Content-Security-Policy" in resp.headers


def test_frame_src_takes_the_grafana_origin_when_set():
    assert csp_frame_src(SimpleNamespace(GRAFANA_ORIGIN="")) == []
    assert csp_frame_src(SimpleNamespace(GRAFANA_ORIGIN="https://grafana.example")) == [
        "https://grafana.example"]
