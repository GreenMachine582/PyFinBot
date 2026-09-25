# Changelog

All notable changes to `PyFinBot`. Versions follow semver (pre-1.0: a breaking change bumps the minor
version). From v0.2.0 on, entries are written by [release-please](https://github.com/googleapis/release-please)
from conventional commits; the same notes are published as
[GitHub Releases](https://github.com/GreenMachine582/PyFinBot/releases).

## [0.2.0](https://github.com/GreenMachine582/PyFinBot/compare/v0.1.0...v0.2.0) (2026-09-25)


### Features

* **transactions:** Transaction.recompute(); partial PUT updates ([f3000db](https://github.com/GreenMachine582/PyFinBot/commit/f3000db9fa073d54415731ae1e8cc8e426a6beab))
* **web:** gth data tables, badges and titled toasts ([35247fb](https://github.com/GreenMachine582/PyFinBot/commit/35247fb64a50ffdd28340910aae1998a876d755e))
* **web:** stocks and transactions pages ([6a490d6](https://github.com/GreenMachine582/PyFinBot/commit/6a490d6a406b70a084683b155f632a684ae2597f))


### Bug Fixes

* **api:** sync the requested market, not always ASX; 409 while a sync runs ([b9a42d6](https://github.com/GreenMachine582/PyFinBot/commit/b9a42d6ebb0cfb7d591eba1086300cd59920260a))


### Build

* **deps:** greentechhub-ui v0.9.0, greentechhub-fastapi v0.8.0 ([79a8360](https://github.com/GreenMachine582/PyFinBot/commit/79a83600b77071dcae18f6710deaa90fbbf2838d))

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
