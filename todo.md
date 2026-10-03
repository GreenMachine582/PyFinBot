# PyFinBot TODO

Cross-session backlog — open work only. Phases 0–8 (housekeeping, data
integrity, auth, testing/CI setup, MVP/import/reporting, docs, Commsec email
ingestion, dividend data + reporting) are complete — see `git log` for that
history rather than a checklist here.

## Open items

- [ ] Make mypy blocking in CI — currently advisory (`continue-on-error:
      true`); needs targeted `# type: ignore`s at ~21 known SQLModel/
      SQLAlchemy-typing-friction call sites, or better upstream SQLModel stubs
- [ ] FIFO Method Support — accurate gain/loss computation using FIFO (and
      per-parcel tracking), as an alternative/addition to the current
      average-cost-basis capital-gains calculation
- [ ] CLI Interface — interact via command line with exportable summaries

## Web UI (greentechhub-fastapi / greentechhub-ui)

Full scope, architecture, and phasing: see `web-implementation-brief.md`.
Roughly, in order:

- [x] Pin `greentechhub-fastapi`/`greentechhub-ui` as dependencies; wire
      `register_auth` (`AUTH_ADAPTER=local`) into `pyfinbot.py` — done: web
      login route (credential check + `create_session_cookie`) + base shell
      (`web/templates/`, extending `greentechhub_ui`'s `app.html`) + a
      placeholder dashboard also landed in the same pass, verified via
      `tests/test_web_auth.py` (full session-cookie login→dashboard→logout
      round trip, 7 tests, 100% coverage on the new `web/` routes)
  - [x] `register_core` + `Settings` extending `GTHBaseSettings` — done:
        `Settings` now extends `GTHBaseSettings`, `CORS_ORIGINS` renamed to
        `CORS_ALLOWED_ORIGINS` (matching what `register_core` reads), the
        hand-rolled CORS middleware + `cors_origins_list` retired in favor
        of `register_core(app, settings)` (also picks up request-id/timing/
        security-header/trusted-proxy middleware for free)
- [x] Stocks + Transactions pages — `gth_data_table` (sortable headers,
      `gth_table_filter`, load-more paging, refreshed on change), modal
      create/edit/delete, ASX sync action with titled toasts, `gth_badge`
      status/type pills, searchable stock picker; transactions are fully
      editable (derived fields recomputed via `Transaction.recompute()`, which
      `PUT /api/transactions/{id}` now uses too); covered by
      `tests/test_web_stocks.py`/`test_web_transactions.py`
- [x] Import page — upload + `gth-toast` — done: `/import` posts the file
      over HTMX and swaps in a result card (row/imported/skipped badges, a
      Row/Problem table for skipped rows) with a success/warning/danger toast
      that also fires `transactionsChanged`; the import itself moved to
      `core/transaction_import.py`, shared with `POST /api/transactions/import`
      (which also returns structured `row_errors` now); covered by
      `tests/test_web_import.py`
- [x] Emails + Dividends pages — manual sync triggers + `gth-toast` — done:
      `/emails` (Sync Commsec emails, with a not-configured hint) and
      `/dividends` (sync all my stocks, or one picked stock) swap in a result
      card with badges + a problems list and a toast; each sync takes a
      `sync_guard` lock so a double-click can't run two at once. The logic
      moved to `core/commsec_import.py` / `dividend_sync.user_stock_ids`,
      shared with the API routes; covered by `tests/test_web_emails.py` /
      `test_web_dividends.py`
- [x] Reports page — holdings, capital gains, and dividend income — done:
      `/reports` with lazy `gth_tabs` panes (holdings as-of date, capital
      gains by FY, dividend income by FY or all time), `gth_stat_card`
      totals + tables, and a CSV download per report for its current
      filter; the computations moved to `core/reports.py`, shared with
      `/api/reports/*`; covered by `tests/test_web_reports.py`
- [ ] Dashboard placeholder — `gth-stat-card`s + empty Grafana iframe slot
- [ ] Later: swap `AUTH_ADAPTER=forward_auth` once Authentik is live (needs
      `register_core`'s `TRUSTED_PROXIES` wired first); real Grafana panels
      once embedding is configured

## greentechhub v0.12 adoption: settings, roles, email accounts

greentechhub-core v0.7.0, -fastapi v0.9.0 and -ui v0.12.0 shipped settings, roles, the user menu and the brand
theme; core v0.8.0, -fastapi v0.10.0 and -ui v0.13.0 then shipped secret settings (gth roadmap #18–#20) and the
landing page, so nothing here waits any more. One PR per item, in this order. The
greentechhub-ui v0.11.0 adoption below continues after item 6, each PR tested against item 2's seed data. Same bar as
the v0.11 items: each PR's tests in their own new file, `pytest` (coverage ≥ 80), `ruff check src tests` and
`mypy src/pyfinbot`.

- [x] 1. `build(deps): greentechhub core v0.8.0, fastapi v0.10.0, ui v0.13.0` — done: core pinned directly with
  `[sqlalchemy]`; `tests/test_gth_versions.py` guards the pins. SQLAlchemy 2.1 (Dependabot #17) is ignored in
  `dependabot.yml` until sqlmodel supports it.
  - Pin `greentechhub-core[sqlalchemy] @ git+…@v0.7.0` directly; the code imports `greentechhub_core.*` but only
    gets core through fastapi today. Bump fastapi to `@v0.9.0` and ui to `@v0.12.0`, then reinstall `.venv` (it has
    core **0.6.0**).
  - No API changes are needed; both releases are additive. ui 0.12 changes the look, so check every page:
    - the brand accent: `btn-primary`, links, focus rings and checked inputs turn brand green;
    - `gth_segmented` without option styles becomes the track;
    - the favicon is a tile.
  - Settle Dependabot #17 (SQLAlchemy 2.1) against core's `[sqlalchemy]` extra (`sqlalchemy>=2`).
- [x] 2. `feat(dev): demo data seed`, so there's realistic data to test every following PR — done:
  `python scripts/seed_demo.py [--reset]` (`src/pyfinbot/dev/seed.py`), logins in the README.
  - `scripts/seed_demo.py`:
    - creates `demo-admin` and `demo-user` with known dev passwords;
    - creates about 8 ASX stocks, some archived;
    - adds about 150 transactions over three financial years, buys and sells, enough to page;
    - adds dividends and a few notes.
  - It's idempotent (`--reset` wipes the demo rows) and refuses to run unless `ENVIRONMENT == "development"`.
  - README "Development": run it, then log in.
  - Tests: two runs don't duplicate; it refuses in production; it produces the expected counts.
- [x] 3. `feat(settings): user preferences, settings page and the user menu` — done: `core/user_settings.py`
  (core's preferences, with PyFinBot's own defaults of 50 rows per page and "31 Jan 2026" dates), migration
  `c41d8e2f7a90` (`gth_settings`), and the test client points the store at its connection via
  `set_session_factory_override`.
  - `db/session.py`: expose `get_session_factory()` (an `async_sessionmaker`); `get_session()` is unchanged.
  - `settings_table(SQLModel.metadata)` in `models/`, plus migration 4 (`gth_settings`).
  - `register_settings(app, settings, registry=SettingsRegistry(USER_PREFERENCES),
    store=SQLAlchemySettingsStore(table, async_session_factory=…), views=SettingsViews(templates=templates),
    logout_url="/logout")`. No `manage_permission` yet; item 5 adds the App section.
  - `web/templating.py`: add `settings_context` to `context_processors`. That brings the user menu (Settings, Log
    out), the server-saved theme and `user_settings`, so `|date`, `|money` and `|number` follow the user. Remove
    `dashboard.html`'s hand-built logout form.
  - `routes/stocks.py`/`transactions.py`: `TableState.from_query(..., user_settings=…)` (via
    `get_effective_settings`), so rows per page follow the user. CSV exports keep the plain formats.
  - conftest: `register_settings` adds middleware and doesn't use `dependency_overrides`, so
    `_ensure_auth_registered` is unaffected. The store opens its own sessions, so the `client` fixture overrides
    `db.session.get_session_factory` to its per-test connection.
  - Tests: needs login; preferences persist per user; the user menu logs out; page size follows the setting.
- [x] 4. `feat(email): per-user email accounts for Commsec sync` — done: the "Email sync" settings group
  (`core/user_settings.py`), `core/email_accounts.load_email_account`, a per-user sync lock, and
  `SETTINGS_CIPHER_KEY` (derived from `SECRET_KEY` when unset). Old `GMAIL_*` env vars warn and are ignored.
  - Today one server-wide mailbox (`GMAIL_*`) is imported as whichever user clicks Sync. This moves the account into
    each user's settings.
  - Add core's `[crypto]` extra (the pins are already at core v0.8.0 / fastapi v0.10.0 / ui v0.13.0). Add a `SETTINGS_CIPHER_KEY` setting (a Fernet key) and pass
    `FernetCipher` to `register_settings(cipher=…)`.
  - An "Email sync" group of USER settings:
    - `email.address`;
    - `email.app_password` (secret: write-only in the form, encrypted at rest);
    - `email.imap_host` (`imap.gmail.com`), `email.imap_port` (993), `email.mailbox` (`INBOX`);
    - `email.commsec_sender` (`bounceback@commsec.com.au`).
  - `core/email_sync.py`'s `fetch_commsec_emails`/`mark_seen` take an `EmailAccount` value instead of reading the
    globals. The `/emails` page and `POST /api/emails/sync` load the current user's account (through
    `Settings.get` and `get_secret`).
  - The Emails page links to Settings when the account isn't configured.
  - **Breaking config change:** remove `GMAIL_*`/`COMMSEC_SENDER` from `Settings`, the README, `.env` examples and
    docker-compose.
  - Tests:
    - two users each sync only their own mailbox (mocked IMAP);
    - the password is encrypted in `gth_settings` and appears in no page HTML;
    - a blank password on save keeps the stored one;
    - not configured gives a link to Settings.
- [x] 5. `feat(permissions): roles, the admin pages and a locked-down users API` — done: `core/permissions.py`
  (admin: `users.manage`, `settings.manage`), `ROLE_BOOTSTRAP`/`ROLE_GROUPS`, migration `d52e9f3a8b17`
  (`gth_role_grants`), `/admin/roles`, Settings › App (the site banner), `require_api_permission` on the users API,
  `scripts/create_user.py`, and the seed makes `demo-admin` an admin. Tests create users directly
  (`conftest.create_user`) and grant roles with `make_admin`.
  - The role catalogue: `ADMIN = Role("admin", {users.manage, settings.manage})`. Plus a `ROLE_BOOTSTRAP` setting
    (e.g. `demo-admin=admin`).
  - `role_grants_table(SQLModel.metadata)` plus migration 5. `register_permissions(app, settings, roles=ROLES,
    grants=SQLAlchemyGrantStore(…))`.
  - `manage_permission="settings.manage"` turns on Settings › App; `RoleAdminViews(templates=…,
    permission="users.manage")` serves `/admin/roles`. Both get nav items with `required_permission`.
  - **Users API:** `GET /api/users/` and `POST /api/users/` require `users.manage`. That needs a bearer-JWT twin of
    `require_permission`: resolve the `User`, build an `Identity`, and call the app's resolver.
    - The first user comes from the seed, or a `create-user` script plus `ROLE_BOOTSTRAP`.
    - Update `tests/conftest.py`'s `register_and_login()`, which relies on open registration.
  - Closes the two users-API "Known limitations" below, and updates `web-implementation-brief.md` §2 and §10.
  - Tests: the bootstrap admin reaches Settings › App and Roles; a normal user gets 403 and no admin nav; the users
    API returns 403 without `users.manage`.
- [x] 6. `chore(web): adopt register_logging, register_health and register_exception_handlers` — done: JSON logs
  via core's `configure_logging` (with `service`/`version`, which `register_logging` doesn't pass), `/health` and
  `/health/ready` (`db.session.database_ready`, plus a docker-compose healthcheck), and every `/api` error as the
  `{code, message, details}` envelope at its old status (`core/errors.StatusError` for 400/502/503,
  `web/api_errors.py` for the 401 challenge, framework errors and validation). Pages keep FastAPI's defaults.
  - Structured JSON logs, `/health` with core's `check_database` against the async engine, and JSON error envelopes
    for `/api`. The pages' login redirect and HX-Redirect flow must be unchanged.
- [ ] 7. Then the greentechhub-ui v0.11.0 adoption below: #21 (date range presets, open) first, then the rest in order.

## greentechhub-ui v0.11.0 adoption

> Continues after items 1–6 of "greentechhub v0.12 adoption" above (item 7 there). Test each PR against the demo
> seed (item 2).

v0.11.0 (the Data & forms release) adds date range presets, file drop, bulk
selection, column view options, CSV export URLs, form-field extras and shared
`money`/`number`/`date` filters. One PR per item, in this order (item 1 first:
the rest need the pin). Each PR puts its tests in its own new test file, and
must pass `pytest` (coverage ≥ 80), `ruff check src tests` and
`mypy src/pyfinbot`.

- [x] `build(deps): greentechhub-ui v0.11.0; shared formatting filters` —
      done; covered by `tests/test_web_formatting.py`. Pin `@v0.11.0` in `requirements.txt` and reinstall the local `.venv`
      (it currently has gth-ui **0.6.0**, not the pinned 0.10.0). Drop
      `_money`/`_qty` from `web/templating.py` (keep `_fy`; gth has no FY
      filter) — `install()` supplies `money`/`number`/`date`, and our own
      assignments after it would shadow them. `|qty` and `|string|qty` →
      `|number` (it takes the report schemas' floats directly). `|money` call
      sites stay but now print `$` (`-$264.95` for a buy's cost); per-unit
      prices (Price, Per share) stay `|number` so they keep full precision.
      Raw dates → `|date` ("5 Feb 2025"): the transaction table's
      `strftime("%d/%m/%Y")`, ex/pay dates in `_report_dividends.html`, the
      holdings empty state (keep the ISO `as_of` for input values and CSV
      hrefs). Update `test_web_reports.py:88,152` for the new date format
- [x] `feat(transactions): date range presets` — done; covered by
      `tests/test_web_date_range.py`. `gth_date_range` replaces
      `transactions.html`'s hand-built From/To inputs (`hide_label=True`,
      `field_class="mb-0"`, `fy_start_month=7` default); same
      `date_from`/`date_to` params, so the route is unchanged. Keep the FY
      select
- [x] `feat(import): drag-and-drop upload with a 5 MB limit` — done; covered by
      `tests/test_web_import_file_drop.py`. The limit is `core.transaction_import.read_upload` (413 via
      `ImportFileError`), shared with `POST /api/transactions/import`. Originally:
      `gth_file_drop("file", "File", accept=ACCEPTED_EXTENSIONS,
      max_size=MAX_UPLOAD_BYTES)` in `import.html` (the form already has
      `hx-encoding`); `MAX_UPLOAD_BYTES = 5 * 1024 * 1024` in
      `core/transaction_import.py`; `imports.py` reads at most limit + 1 bytes
      and raises `ImportFileError("File is larger than 5 MB.")` — the existing
      422 result panel + toast. Update `test_web_import.py:42`'s `accept`
      assertion
- [ ] `feat(transactions): CSV export and column view options` — split
      `_query_transactions` into a statement builder + paging so a new
      `GET /transactions.csv` takes the table's filters and sort with no paging
      (the `reports.py` CSV pattern; `pyfinbot-transactions.csv`: Date, Market,
      Symbol, Type, Units, Price, Fees, Total, Cost, FY, Notes; user-scoped);
      `export_base_url="/transactions.csv"` on `_table_state`. The 11-column
      table gets `view_options=True`: Date and Stock `hideable: False`, Notes
      `hidden: True`. Done as item 2 of "greentechhub adoption" below, after
      the ui v0.14 pin: the blank `""` actions header would show in the View
      menu as an unlabelled, hideable toggle, so the same PR swaps both
      tables' hand-built edit/delete buttons for `row_actions=True` +
      `gth_table_actions_cell`
- [ ] `feat(stocks): bulk archive and unarchive` — `POST /stocks/bulk-archive`
      and `/stocks/bulk-unarchive` read `ids` and share `update_stock`'s
      `is_active`/`archived_at`/`write_datetime` rules (factor them into one
      helper); toast "Archived 3 stocks" + `stocksChanged`.
      `_stock_table.html`: `bulk_actions` + `gth_table_select_cell`. (Stocks
      are global, not per-user, like the existing stock routes)
- [ ] `feat(web): form polish` — `_transaction_form.html`: `prefix="$"` on
      Price and Fees; Notes → `type="textarea", rows=3, maxlength=500`.
      `notes` gets `max_length=500` in the create/update schemas (the form's
      422 re-render shows the error; the API enforces it too) via a shared
      `NOTES_MAX`; the CSV importer and Commsec email import truncate notes to
      500 instead of failing the row. No DB migration (enforced in the app).
      `_stock_form.html`: `maxlength=20` on symbol and market (the model's
      limit)
- [ ] `feat(transactions): bulk delete` — **after the CSV export item** (same
      route and table files). `POST /transactions/bulk-delete` reads `ids` and
      deletes only the current user's rows (a user-scoped query, so another
      user's ids are silently ignored, like the 404-not-403 single delete);
      toast "Deleted N transactions" + `transactionsChanged`. The table gets
      `bulk_actions=[{"label": "Delete", "style": "btn-outline-danger",
      "confirm": "Delete the selected transactions?", ...}]` + select cells

## greentechhub adoption: ui v0.14, core v0.9, fastapi v0.11 (slimming PyFinBot)

> From a review of PyFinBot's web layer (2026-10-03): hand-rolled pieces that belong in the gth repos moved there
> (opt-in), and PyFinBot drops its copies. One PR at a time, in this order; each puts its tests in its own new test
> file and must pass `pytest` (coverage ≥ 80), `ruff check src tests` and `mypy src/pyfinbot` (≤ 55 errors).

Shipped in the gth repos:
- [x] greentechhub-ui v0.14.0 — row actions (#61), submit busy buttons (#62), inline `gth_alert` (#63),
  `gth_select(hide_label=True)` (#64), a branded `login_page.html` on `layout="auth"` (#65)
- [x] greentechhub-core v0.9.0 — `ApplicationError(status_code=…)` + `BadRequestError` (#28),
  `site_banner_settings()` (#29), `sqlalchemy.order_by`/`paginate` (#30), `FilterGroup` + `where` (#32),
  `page()` (#33), `dates` fiscal years (#34)
- [x] greentechhub-fastapi v0.11.0 — the status hint + `BadRequestError` honoured (#27),
  `register_api_error_handlers` (#28), the opt-in site banner (#29), JSON filter groups (#30), `LoginViews`
  defaulting to ui's login page (#31)

PyFinBot, in order:
- [x] 1. `build(deps): greentechhub ui v0.14, core v0.9, fastapi v0.11` — done; covered by
  `tests/test_web_login_page.py`. Pin all three in `requirements.txt`.
  fastapi v0.11's `LoginViews` renders ui's `login_page.html` and `PyFinBotLoginViews` doesn't override it, so the
  bump itself switches the login page: delete `web/templates/login.html` in the same PR. Check nothing else moves:
  core v0.9's `status_code` hint is read by fastapi's handlers, and `StatusError` already carries a matching
  `status_code`, so API statuses must stay as they are
- [ ] 2. `feat(transactions): CSV export and column view options` (the v0.11 item above), with
  `row_actions=True` + `gth_table_actions_cell` replacing the hand-built edit/delete cells on the transactions
  **and** stocks tables
- [ ] 3. `refactor(web): adopt gth_alert, submit busy buttons and gth_select`:
  - the raw alerts in `emails.html` (×2), `_sync_result.html` and `_import_result.html` → `gth_alert`;
  - the hand-copied busy submit buttons in `import.html` and `dividends.html` → `gth_busy_button(submit=True)`;
  - the filter-bar selects in `transactions.html`/`stocks.html` and the report panes' FY/as-of fields →
    `gth_select(hide_label=True)` / `gth_form_field`
- [ ] 4. `refactor(api): fastapi's API error handlers` — `register_api_error_handlers(app, prefix="/api")` replaces
  `web/api_errors.py`; `StatusError` raises become core's `BadRequestError` or
  `ApplicationError(..., status_code=…)`, deleting `core/errors.py`. The existing envelope tests hold unchanged
- [ ] 5. `refactor(web): the site banner from core + fastapi` — `*site_banner_settings(edit_permission=SETTINGS_MANAGE)`
  replaces the hand-written `site.banner`/`site.banner_tone` definitions (same keys, so saved values carry over), and
  fastapi's `settings_context` replaces `templating.site_banners_context`
- [ ] 6. `refactor(query): core's where / order_by / page` — the web tables use `order_by` + `paginate` (deleting
  `web/paging.py` and `core/sorting.py`); the API list routes use `PageParams` / `parse_filter_json` + `page()`
  (deleting `core/sa_filters_compat.py`). Check whether anything still sends the Tabulator `sorters` JSON: convert it
  to `Sort`s, or drop it if nothing does
- [ ] 7. `refactor(core): core's fiscal years` — `greentechhub_core.dates` replaces `core/fiscal_year.py`; the `|fy`
  filter uses `fiscal_year_label`
- [ ] 8. `refactor(core): core's password hashing` — `greentechhub_core.security.passwords` replaces the bcrypt
  helpers in `core/security.py`; same bcrypt format, so existing hashes still verify (test it)

The remaining greentechhub-ui v0.11.0 items above (stocks bulk archive, form polish, transactions bulk delete) follow
these.

## Known limitations (accepted, not bugs)

- Stateless JWT, 24h expiry, no refresh/revocation — a leaked token is valid
  up to 24h with no force-logout. Acceptable for personal-use scale; would
  need a blocklist or refresh tokens to harden.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
