# Changelog

All notable changes to `PyFinBot`. Versions follow semver (pre-1.0: a breaking change bumps the minor
version). From v0.2.0 on, entries are written by [release-please](https://github.com/googleapis/release-please)
from conventional commits; the same notes are published as
[GitHub Releases](https://github.com/GreenMachine582/PyFinBot/releases).

## [0.1.0](https://github.com/GreenMachine582/PyFinBot/releases/tag/v0.1.0) (2026-09-25)

Baseline for release-please: everything built before versioning started. (The code at this tag still says
1.0.0 in `version.py` — versioning restarted at 0.1.0 afterwards.)

### Features

* **api:** stocks, transactions and users with JWT auth and per-user ownership; holdings, capital-gains and
  dividend income reports; CSV/Excel transaction import with duplicate skipping.
* **sync:** ASX market sync, Commsec confirmation-email ingestion, yfinance dividend sync.
* **web:** session-cookie login and dashboard shell on greentechhub-ui.
* **core:** `register_core` + `GTHBaseSettings` (greentechhub-fastapi / -core); Alembic migrations on startup.
* **build:** Docker image on `python:3.12-slim`; CI with pytest, coverage, ruff and mypy.
