# PyFinBot TODO

Cross-session backlog. Check items off as completed, add new ones as they're discovered. Organised by phase — work roughly top to bottom, but phases aren't strictly sequential.

## Phase 0 — Housekeeping (do first)

- [x] Commit the currently uncommitted work: `tests/`, `pytest.ini`, `import_routes.py`, `report_routes.py`, the squashed alembic migration, and the modified core/api/schema files
- [x] Fix route prefix collision: `transaction_routes.py` and `import_routes.py` both register `APIRouter(prefix="/transactions")` — added `:int` path converters to `transaction_routes.py`'s `{transaction_id}` routes so they can never shadow `/transactions/import`. Verified: full pytest suite green (105 passed) using the project's `.venv` (Python 3.14)
- [x] Rename `core/dependacies.py` → `core/dependencies.py` (typo)
- [x] Fix `Dockerfile` CMD — points at `server.wsgi:application` (Django-style, doesn't exist); now runs `uvicorn src.pyfinbot.pyfinbot:app`, matching `docker-compose.yml`
- [x] Fix `Dockerfile` bind address typo `000.0.0.0:8001` → `0.0.0.0:8001` (fixed as part of the CMD rewrite above)

## Phase 1 — Data integrity & correctness

- [x] Fix CSV/Excel import building `Transaction` directly with a raw date string, bypassing all date parsing — `Transaction.model_post_init` crashed computing `fy` (`'str' object has no attribute 'month'`) on every row. Fixed by extracting `parse_transaction_date` out of `TransactionBase`'s validator into a shared function (`schemas/transaction_schemas.py`) and calling it from `import_routes.py`
- [x] Fix CSV/Excel import treating empty cells as pandas `NaN` (truthy, unlike `None`) instead of `None` — broke `value or default` fallbacks and violated the `fees` column's `NOT NULL` constraint. Fixed in `_parse_dataframe` by casting to `object` dtype before replacing `NaN` with `None` (plain `.where(pd.notna(df), None)` doesn't stick on numeric-dtype columns — pandas silently re-coerces `None` back to `NaN`)
- [x] Wire app startup to run Alembic migrations (`alembic upgrade head`) instead of `init_db()` calling `SQLModel.metadata.create_all` — `db/session.py`'s `init_db()` now runs `alembic.command.upgrade(cfg, "head")` off the event loop via `asyncio.to_thread`, with `script_location`/`prepend_sys_path` overridden to absolute paths so it's not dependent on the process's CWD (unlike the documented CLI workflow). Verified with an isolated SQLite smoke test (migration runs, creates the 3 tables + `alembic_version`, is idempotent on a second run) — not run against the real `.env`-configured database
- [x] Make SQL echo logging (`create_async_engine(..., echo=True)` in `db/session.py`) env-driven instead of hardcoded on — added `DB_ECHO: bool = False` to `core/settings.py`, defaulting off (was unconditionally logging full SQL + parameter values, a real concern in production)
- [x] Add dedupe/idempotency check to `import_routes.py` so re-uploading the same file doesn't create duplicate transactions — app-level pre-insert check only (not a DB-wide unique constraint, to avoid blocking legitimate identical re-entries via the manual create endpoint), keyed on `(user_id, stock_id, transaction_date, type, units, price, fees)`; catches both re-uploads and duplicate rows within the same file, since it queries against the session after each row's flush
- [x] Move the inline `BaseModel` schemas in `report_routes.py` / `import_routes.py` into `schemas/`, matching the Base/Create/Update/Read pattern used elsewhere — new `schemas/report_schemas.py` (`HoldingItem`, `HoldingsReport`, `CapitalGainsItem`, `CapitalGainsReport`) and `schemas/import_schemas.py` (`ImportSummary`), both wired into `schemas/__init__.py`; pure relocation, no behavior change
- [x] Minor: `Stock.search()` (`models/stock_models.py:32`) uses `session.execute()` instead of SQLModel's `session.exec()`, and `stock_routes.py`/`transaction_routes.py`'s list endpoints call fastapi-pagination's deprecated `paginate()` instead of `apaginate()` — both swapped over (`.scalar_one_or_none()` → `.one_or_none()` to match, since `session.exec()` returns a `ScalarResult` not a `Result`). Warning count dropped from 66 to 4 per test run; the remaining 4 originate inside the `fastapi_pagination` library itself (`ext/sqlalchemy.py:310`), not app code — out of scope

## Phase 2 — Auth & security

- [x] Decide on an auth approach (session/JWT/OAuth2) for multi-user support — JWT bearer tokens via `OAuth2PasswordBearer` (FastAPI's own idiomatic pattern): stateless, no session-store infra needed, free `/docs` Swagger "Authorize" button
- [x] Wire up the existing but unused `hash_password` / `verify_password` in `core/security.py` — now called from `user_routes.py` (register/change password) and `auth_routes.py` (login)
- [x] Add login/token issuance endpoints — `POST /api/auth/login` (`auth_routes.py`), `OAuth2PasswordRequestForm`, issues a JWT signed with `SECRET_KEY` (`ALGORITHM = "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES = 1440`). Registration reuses the existing `POST /users/` rather than a separate `/auth/register` — `UserCreate.password`/`UserUpdate.password` added instead of a parallel endpoint
- [x] Replace the spoofable `X-User-ID` header mechanism with enforced authentication on user/transaction routes — `x_user_id_dep` removed entirely; `get_current_user` (`core/dependencies.py`) decodes the JWT and loads the real `User`, used across all 8 former call sites (`transaction_routes.py` ×5, `report_routes.py` ×2, `import_routes.py` ×1) plus newly added to `user_routes.py`'s own CRUD (previously had zero ownership checks). Also closed a real spoofing gap: `create_transaction` used to trust a client-supplied `transaction_in.user_id` over the header — `user_id` is now removed from `TransactionBase` entirely and always comes from the authenticated token. The `_ensureUser`/`_ensure_user` auto-create-on-first-transaction functions were removed (dead once every route requires an already-registered, authenticated user)
- [x] Add CORS and env-mode (dev/prod) settings to `core/settings.py` — new `ENVIRONMENT` (`"development"`/`"production"`) and `CORS_ORIGINS` (comma-separated allow-list) settings, plus `CORSMiddleware` registered in `pyfinbot.py`. `development` allows all origins when `CORS_ORIGINS` is unset (frictionless local/Swagger testing); `production` allows none by default and emits a startup warning if `CORS_ORIGINS` is left unset, mirroring the existing `SECRET_KEY` unsafe-default pattern. Also extracted the `.env` variable layout out of README's inlined prose into a tracked `.env.example`

### Accepted scope boundaries / risks from the auth implementation
- `GET /users/` (`list_users`) requires *a* valid token but returns every user unfiltered — no admin/RBAC system was built; deliberate scope boundary, not an oversight
- Stateless JWT, 24h expiry, no refresh/revocation — a leaked token is valid for up to 24h with no way to force-logout. Acceptable for a personal-use app; would need a token blocklist or short-lived+refresh tokens to harden
- `SECRET_KEY` defaults to a random value generated fresh on every process start (not a hardcoded/empty fallback, which would be a silent security hole) — a real deployment that needs tokens to survive a restart must set `SECRET_KEY` explicitly in `.env` (a startup warning fires when it's unset)

## Phase 3 — Testing & CI

- [x] Fix `tests/conftest.py`'s `engine` fixture calling `SQLModel.metadata.create_all` before any model module was ever imported, so it silently created zero tables (`sqlite3.OperationalError: no such table: user`). Fixed by importing `pyfinbot.models` at module load time in `conftest.py`
- [x] Fix per-test DB rollback not actually isolating tests (data from one test was visible in the next) — root cause is a well-known pysqlite/aiosqlite quirk where the driver autocommits outside of DML statements, defeating SAVEPOINT-based isolation unless the SQLAlchemy-documented event-listener workaround is applied. Added to the `engine` fixture in `conftest.py`
- [x] Fix `conftest.py` importing plain `sqlalchemy.ext.asyncio.AsyncSession` instead of `sqlmodel.ext.asyncio.session.AsyncSession` — caused `AttributeError: 'AsyncSession' object has no attribute 'exec'` in every route that calls `session.exec(...)` (the app itself uses the SQLModel session everywhere)
- [x] Re-enable `.github/workflows/general_tests.yml` (currently fully commented out) and update it to run the pytest suite, not the stale `unittest discover` command — also bumped `actions/checkout`/`actions/setup-python` from `v2` to `v4`/`v5` (the old versions rely on deprecated GitHub Actions runtimes)
- [x] Add lint/type-checking (e.g. ruff + mypy) and wire into CI — new `pyproject.toml` with `[tool.ruff]`/`[tool.mypy]` config, separate `lint` job. Ruff is blocking and fully clean (found and fixed genuine issues: unused imports in `__init__.py` re-exports via `as` alias, an unused exception variable, missing `TYPE_CHECKING` forward-ref imports on `Stock`/`User` models, `alembic/env.py` excluded as Alembic-generated scaffolding). **Mypy is advisory only** (`continue-on-error: true`) — it reports 21 pre-existing findings, all confirmed to be inherent SQLModel/SQLAlchemy typing-system friction (even with SQLAlchemy's own mypy plugin enabled), not real bugs; making it blocking would need either scattering many targeted `# type: ignore`s across ORM code or a real typing refactor, disproportionate to this task
- [x] Add test coverage reporting — `pytest-cov` added, `pytest.ini` now runs with `--cov-report=term-missing --cov-fail-under=80` (measured baseline was 87%; 80% is a regression guard, not an aspirational target)
- [ ] Make mypy blocking in CI (currently advisory, see above) — needs either targeted `# type: ignore`s at the 21 known SQLModel/SQLAlchemy-typing-friction call sites (`Field(sa_type=...)` overloads, `Model.id.in_(...)`, `selectinload(Model)`, `apaginate(session, stmt)`, `order_by(col, col)`), or waiting for better upstream SQLModel type stubs

## Phase 4 — Feature milestones

Mirrors and supersedes the README's "Planned Milestones" list, which is now out of date.

- [x] MVP — schema design, transaction insertion, SQL-based queries
- [x] Import System — CSV/Excel import of stock transactions (`import_routes.py`)
- [x] Reporting Module — FY-based holdings & capital-gains reports (`report_routes.py`, average cost basis)
- [ ] FIFO Method Support — accurate gain/loss computation using FIFO (and per-parcel tracking), as an alternative/addition to average cost basis
- [ ] CLI Interface — interact via command line with exportable summaries
- [ ] Web Dashboard (optional) — simple front end to view/interact with data

## Phase 5 — Documentation polish

- [x] Update README's Planned Milestones section to match Phase 4 above (Import/Reporting are done, not "planned")
- [x] Update README's Testing section — replace `python -m unittest discover -s tests` with the pytest invocation
- [x] Note in README that `todo.md` is the live project backlog
- [x] Broader README pass: fixed the dead CI badge link, added License/Python/FastAPI/SQLModel badges, and added Tech Stack, Project Structure, Getting Started, and API Overview sections (previously had no setup instructions at all)

## Phase 6 — Commsec email ingestion

- [x] Add Gmail IMAP settings to `core/settings.py` — `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `GMAIL_IMAP_HOST` (default `imap.gmail.com`), `GMAIL_IMAP_PORT` (default `993`), `GMAIL_MAILBOX` (default `INBOX`), `COMMSEC_SENDER` (default `bounceback@commsec.com.au`, confirmed from a real Commsec confirmation email's `From:` header). Uses a Gmail App Password over `imaplib` (stdlib), not the OAuth Gmail API — simplest option, no Google Cloud project needed
- [x] Extract `_is_duplicate` out of `import_routes.py` into `core/dedupe.py` (`is_duplicate_transaction`) so both the CSV/Excel importer and the new email importer share one dedup implementation instead of one importing the other's `_`-prefixed internal
- [x] Add `core/email_sync.py` — synchronous IMAP fetch (`fetch_commsec_emails`, run via `asyncio.to_thread`), multipart body extraction with `text/plain` → BeautifulSoup-stripped `text/html` fallback (`extract_body`), and `received_at()` which parses the email's `Date` header as a trade-date stand-in (Commsec's confirmation emails have no explicit trade-date field, but are sent promptly after the trade)
- [x] Add `core/commsec_parser.py` (`parse_commsec_email`) — built and verified against two real Commsec confirmation emails (a buy and a sell). This email format has no contract-note/reference number, so dedup relies on content matching (`user_id, stock_id, transaction_date, type, units, price, fees`) rather than a unique reference; brokerage isn't stated directly and is derived as `|total_settlement − units×price|`; subject and body are cross-checked (action/symbol/units) and raise `CommsecParseError` on mismatch or missing fields. Other Commsec email types (partial fills, DRP, managed funds, corporate actions) are untested against this parser and will surface as errors rather than being mis-parsed
- [x] Add `POST /api/emails/sync-commsec` (`api/email_routes.py`, optional `?include_seen=` for debugging) — fetches unseen Commsec emails, parses each, resolves the stock via `_searchForStock` as `ASX:{symbol}`, builds a `Transaction`, dedupes, commits once, marks only successfully-processed messages `\Seen` (so parse/lookup failures keep retrying next sync rather than being silently dropped). Returns `EmailSyncSummary`; 503 if Gmail credentials unset, 502 on IMAP failure. Matches the manual-trigger pattern of `POST /api/stocks/sync/{market}` — no scheduler/cron added
- [x] Add `tests/fixtures/commsec_emails/{bought_rmd,sold_wow}.txt` (built directly from the real sample emails), `tests/test_commsec_parser.py` (15 tests: field extraction, derived brokerage, error cases), `tests/test_email_sync.py` (8 tests: IMAP mocked, dedup on resync, 503/502 error paths, unknown-stock and unparseable-email handling). Verified: full pytest suite green

## Phase 7 — Dividend data

- [x] Add `Dividend` model (`models/dividend_models.py`) — stock-scoped, not user-scoped: `stock_id` FK, `ex_date`, `pay_date`, `amount_per_share` (`Numeric(18,6)`), `source`, unique on `(stock_id, ex_date)`. A dividend is a stock-level market fact shared across all holders; per-user "amount received" is computed on read in `report_routes.py` rather than stored, matching how holdings/capital-gains are already computed live from `Transaction` rows instead of cached. Wired into `Stock.dividends` relationship and `models/__init__.py`
- [x] Generate Alembic migration `a7ab2f6a51dc_add_dividend_table.py` via `alembic revision --autogenerate` against an isolated SQLite smoke DB (not the real Postgres DB) — verified `alembic upgrade head` and `alembic downgrade -1` both apply cleanly
- [x] Add `core/holdings.py` (`units_held_as_of`) — the weighted BUY−SELL logic extracted from `get_holdings`, reused for dividend-total calculations so it isn't reimplemented a third time
- [x] Add `core/dividend_sync.py` — `MARKET_TO_YF_SUFFIX` registry (ASX only, matching `market_sync.py`'s existing market-coverage limitation), `fetchDividendsForSymbol` (yfinance `Ticker.dividends`), `syncDividends` upsert keyed on `(stock_id, ex_date)`, following `market_sync.py`'s injectable-fetcher pattern
- [x] Add `POST /api/dividends/sync` (`api/dividend_routes.py`, optional `?stock_id=`) — defaults to every stock the calling user has ever transacted (not the full `Stock` table, to avoid a slow/rate-limited full-market yfinance fetch)
- [x] Add `tests/test_dividend_sync.py` (7 tests: create/update/no-op/isolation/error handling, mocked fetcher) and `tests/test_dividends.py` (4 tests: endpoint integration, stock-id targeting). Verified: full pytest suite green

## Phase 8 — Dividend reporting

- [x] Extract `au_fiscal_year` into `core/fiscal_year.py`; `Transaction.model_post_init` now calls it instead of an inline calc — mechanical, no behavior change, verified against the existing `test_models.py`/`test_transactions.py` suite
- [x] Add `GET /api/reports/dividends?fy=` (`report_routes.py`) — for each `Dividend` belonging to a stock the user has ever transacted, computes units held on the ex-date and the resulting amount received; FY-scoped by `au_fiscal_year(ex_date)` when `fy` given, all-time otherwise. New `DividendItem`/`DividendsReport` schemas in `schemas/report_schemas.py`, mirroring `get_capital_gains`'s FY-scoping style
- [x] Add `total_dividends_received` to `HoldingItem`/`HoldingsReport` — sum of dividends with `ex_date <= as_of`, each weighted by units held on its specific ex-date; additive/backward-compatible field (defaults to `0.0`, not null)
- [x] Extend `tests/test_reports.py` with `TestDividendsReport` (9 tests: before/mid/after-holding weighting, FY filter, multi-stock totals, per-user scoping) and 2 new dividend cases in `TestHoldings`. Verified: full pytest suite green (`test_reports.py` now 26 tests)
