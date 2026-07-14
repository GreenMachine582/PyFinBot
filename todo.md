# PyFinBot TODO

Cross-session backlog. Check items off as completed, add new ones as they're discovered. Organized by phase — work roughly top to bottom, but phases aren't strictly sequential.

## Phase 0 — Housekeeping (do first)

- [x] Commit the currently uncommitted work: `tests/`, `pytest.ini`, `import_routes.py`, `report_routes.py`, the squashed alembic migration, and the modified core/api/schema files
- [x] Fix route prefix collision: `transaction_routes.py` and `import_routes.py` both register `APIRouter(prefix="/transactions")` — added `:int` path converters to `transaction_routes.py`'s `{transaction_id}` routes so they can never shadow `/transactions/import`. Verified: full pytest suite green (105 passed) using the project's `.venv` (Python 3.14)
- [ ] Rename `core/dependacies.py` → `core/dependencies.py` (typo)
- [ ] Fix `Dockerfile` CMD — points at `server.wsgi:application` (Django-style, doesn't exist); should run the FastAPI app like `docker-compose.yml` does (`uvicorn src.pyfinbot.pyfinbot:app`)
- [ ] Fix `Dockerfile` bind address typo `000.0.0.0:8001` → `0.0.0.0:8001`

## Phase 1 — Data integrity & correctness

- [x] Fix CSV/Excel import building `Transaction` directly with a raw date string, bypassing all date parsing — `Transaction.model_post_init` crashed computing `fy` (`'str' object has no attribute 'month'`) on every row. Fixed by extracting `parse_transaction_date` out of `TransactionBase`'s validator into a shared function (`schemas/transaction_schemas.py`) and calling it from `import_routes.py`
- [x] Fix CSV/Excel import treating empty cells as pandas `NaN` (truthy, unlike `None`) instead of `None` — broke `value or default` fallbacks and violated the `fees` column's `NOT NULL` constraint. Fixed in `_parse_dataframe` by casting to `object` dtype before replacing `NaN` with `None` (plain `.where(pd.notna(df), None)` doesn't stick on numeric-dtype columns — pandas silently re-coerces `None` back to `NaN`)
- [ ] Wire app startup to run Alembic migrations (`alembic upgrade head`) instead of `init_db()` calling `SQLModel.metadata.create_all`
- [ ] Make SQL echo logging (`create_async_engine(..., echo=True)` in `db/session.py`) env-driven instead of hardcoded on
- [ ] Add dedupe/idempotency check to `import_routes.py` so re-uploading the same file doesn't create duplicate transactions
- [ ] Move the inline `BaseModel` schemas in `report_routes.py` / `import_routes.py` into `schemas/`, matching the Base/Create/Update/Read pattern used elsewhere
- [ ] Minor: `Stock.search()` (`models/stock_models.py:32`) uses `session.execute()` instead of SQLModel's `session.exec()`, and `stock_routes.py`/`transaction_routes.py`'s list endpoints call fastapi-pagination's deprecated `paginate()` instead of `apaginate()` — both just emit `DeprecationWarning`s today, not broken, but worth cleaning up

## Phase 2 — Auth & security

- [ ] Decide on an auth approach (session/JWT/OAuth2) for multi-user support
- [ ] Wire up the existing but unused `hash_password` / `verify_password` in `core/security.py`
- [ ] Add login/token issuance endpoints
- [ ] Replace the spoofable `X-User-ID` header mechanism with enforced authentication on user/transaction routes
- [ ] Add CORS and env-mode (dev/prod) settings to `core/settings.py`

## Phase 3 — Testing & CI

- [x] Fix `tests/conftest.py`'s `engine` fixture calling `SQLModel.metadata.create_all` before any model module was ever imported, so it silently created zero tables (`sqlite3.OperationalError: no such table: user`). Fixed by importing `pyfinbot.models` at module load time in `conftest.py`
- [x] Fix per-test DB rollback not actually isolating tests (data from one test was visible in the next) — root cause is a well-known pysqlite/aiosqlite quirk where the driver autocommits outside of DML statements, defeating SAVEPOINT-based isolation unless the SQLAlchemy-documented event-listener workaround is applied. Added to the `engine` fixture in `conftest.py`
- [x] Fix `conftest.py` importing plain `sqlalchemy.ext.asyncio.AsyncSession` instead of `sqlmodel.ext.asyncio.session.AsyncSession` — caused `AttributeError: 'AsyncSession' object has no attribute 'exec'` in every route that calls `session.exec(...)` (the app itself uses the SQLModel session everywhere)
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
