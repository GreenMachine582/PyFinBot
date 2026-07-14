# PyFinBot TODO

Cross-session backlog. Check items off as completed, add new ones as they're discovered. Organized by phase — work roughly top to bottom, but phases aren't strictly sequential.

## Phase 0 — Housekeeping (do first)

- [ ] Commit the currently uncommitted work: `tests/`, `pytest.ini`, `import_routes.py`, `report_routes.py`, the squashed alembic migration, and the modified core/api/schema files
- [ ] Fix route prefix collision: `transaction_routes.py` and `import_routes.py` both register `APIRouter(prefix="/transactions")`
- [ ] Rename `core/dependacies.py` → `core/dependencies.py` (typo)
- [ ] Fix `Dockerfile` CMD — points at `server.wsgi:application` (Django-style, doesn't exist); should run the FastAPI app like `docker-compose.yml` does (`uvicorn src.pyfinbot.pyfinbot:app`)
- [ ] Fix `Dockerfile` bind address typo `000.0.0.0:8001` → `0.0.0.0:8001`

## Phase 1 — Data integrity & correctness

- [ ] Wire app startup to run Alembic migrations (`alembic upgrade head`) instead of `init_db()` calling `SQLModel.metadata.create_all`
- [ ] Make SQL echo logging (`create_async_engine(..., echo=True)` in `db/session.py`) env-driven instead of hardcoded on
- [ ] Add dedupe/idempotency check to `import_routes.py` so re-uploading the same file doesn't create duplicate transactions
- [ ] Move the inline `BaseModel` schemas in `report_routes.py` / `import_routes.py` into `schemas/`, matching the Base/Create/Update/Read pattern used elsewhere

## Phase 2 — Auth & security

- [ ] Decide on an auth approach (session/JWT/OAuth2) for multi-user support
- [ ] Wire up the existing but unused `hash_password` / `verify_password` in `core/security.py`
- [ ] Add login/token issuance endpoints
- [ ] Replace the spoofable `X-User-ID` header mechanism with enforced authentication on user/transaction routes
- [ ] Add CORS and env-mode (dev/prod) settings to `core/settings.py`

## Phase 3 — Testing & CI

- [ ] Re-enable `.github/workflows/general_tests.yml` (currently fully commented out) and update it to run the pytest suite, not the stale `unittest discover` command
- [ ] Add lint/type-checking (e.g. ruff + mypy) and wire into CI
- [ ] Add test coverage reporting

## Phase 4 — Feature milestones

Mirrors and supersedes the README's "Planned Milestones" list, which is now out of date.

- [x] MVP — schema design, transaction insertion, SQL-based queries
- [x] Import System — CSV/Excel import of stock transactions (`import_routes.py`)
- [x] Reporting Module — FY-based holdings & capital-gains reports (`report_routes.py`, average cost basis)
- [ ] FIFO Method Support — accurate gain/loss computation using FIFO (and per-parcel tracking), as an alternative/addition to average cost basis
- [ ] CLI Interface — interact via command line with exportable summaries
- [ ] Web Dashboard (optional) — simple front end to view/interact with data

## Phase 5 — Documentation polish

- [ ] Update README's Planned Milestones section to match Phase 4 above (Import/Reporting are done, not "planned")
- [ ] Update README's Testing section — replace `python -m unittest discover -s tests` with the pytest invocation
- [ ] Note in README that `todo.md` is the live project backlog
