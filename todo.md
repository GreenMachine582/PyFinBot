# PyFinBot TODO

Cross-session backlog — open work only. Finished items are removed rather
than ticked; `git log` (and each PR) is the history.

Every PR puts its tests in its own new test file and must pass `pytest`
(coverage ≥ 80), `ruff check src tests` and `mypy src/pyfinbot` (≤ 55 errors).
Test web changes against the demo seed (`python scripts/seed_demo.py`).

When an item needs something the greentechhub repos don't have yet, add it
there first rather than hand-rolling it here. Framework-free pieces go in
core, then fastapi, then ui. Each is released in that order before this repo
bumps its pins in `requirements.txt`. Develop across the repos with local GTH
mode (`scripts/use-local-gth.sh`, see CONTRIBUTING.md); CI always tests the
pins.

## Open items

- [ ] Make mypy blocking in CI
  - **Now:** `mypy src/pyfinbot` reports 52 errors (the cap is 55), and the step in
    `.github/workflows/general_tests.yml` has `continue-on-error: true`.
  - **Most of them:** SQLModel/SQLAlchemy typing friction (column expressions, `session.exec` results),
    about 21 call sites.
  - **Done when:** the count is 0, by targeted `# type: ignore[...]`s with a reason, or by better upstream
    SQLModel stubs, and `continue-on-error` is gone.
- [ ] FIFO method support
  - **Now:** `core/reports.py` uses average cost basis. `holdings_report` takes the weighted average buy price,
    and `capital_gains_report` costs each SELL in the FY at that average.
  - **Plan:**
    - per-parcel lots matched first-in-first-out;
    - the method as a setting (a user preference, or a choice on the reports page) that both reports and their
      API routes honour, defaulting to average so existing numbers don't change.
  - **Done when:** a sell spanning two parcels reports the right gain under FIFO, and average is unchanged.
- [ ] CLI interface
  - Command-line access with exportable summaries (holdings, the FY capital-gains report and dividends, as CSV or
    JSON).
  - **Now:** `scripts/` has `create_user.py` and `seed_demo.py` only.
  - **Plan:** one entry point over the same `core/reports.py` functions, so the CLI and the web never disagree.

## Lean now — no gth release needed

From a review of PyFinBot against the gth repos (2026-10-07): generic code PyFinBot
can drop today, using what the pinned releases already offer. One PR each.

- [ ] `refactor(errors)`: `ImportFileError` (`core/transaction_import.py:51`) and
  `EmailSyncError` (`core/commsec_import.py:29`) subclass core's `ApplicationError`
  with its `status_code` hint, instead of plain `Exception` plus a `status_code`
  attribute. The try/except remapping in `api/import_routes.py` and
  `api/email_routes.py` goes; fastapi's handlers answer them.
- [ ] `refactor(web)`: templates use the ui macros that already exist:
  - `gth_switch` for `_stock_form.html`'s hand-built "Active" checkbox;
  - `gth_segmented(errors=)` for `_transaction_form.html:25`'s error div;
  - `gth_page_header` for `dashboard.html`'s bare `<h2>`;
  - `gth_form` for `dividends.html`'s raw sync `<form>`;
  - `gth_table` for `import.html`'s raw columns `<table>`;
  - the existing `fy_options` filter instead of the inline loops in `_report_gains.html` and
    `_report_dividends.html`.
- [ ] `refactor(auth)`: one password-user module
  - The User lookup + `verify_password` is written twice: `web/routes/auth.py` (with a deferred
    `from ...pyfinbot import app`) and `api/auth_routes.py`.
  - User creation is written three times: `admin/create_user.py`, `api/user_routes.py` and `dev/seed.py`.
  - **Plan:** one `core/users.py` with `check_password(session, user_id, password)` and
    `create_user(session, ...)`.
- [ ] `test`: the local `_create_stock` helpers in 6 test files use conftest's
  `create_stock`

## Web UI (greentechhub-fastapi / greentechhub-ui)

Scope and architecture: see `web-implementation-brief.md`.

- [ ] Dashboard
  - **Now:** a placeholder (`web/templates/dashboard.html`).
  - **Plan:** `gth-stat-card`s (portfolio value, FY realised gain, dividends this FY), then sparklines and an
    embedded Grafana panel.
  - **Waits on:** greentechhub-ui's planned server-rendered charts (`gth_sparkline`, `gth_stat_card` slot) and
    `gth_embed_card` (ui TODO › Display & charts).
- [ ] Switch to `AUTH_ADAPTER=forward_auth` once Authentik is live. The code side is ready:
  `register_core`/`register_auth`, and core's `trusted_proxies`.
  - Set `AUTH_ADAPTER=forward_auth`, `TRUSTED_PROXIES` to the outpost's address, and `ROLE_GROUPS` (e.g.
    `admins=admin`).
  - The local sign-in routes switch themselves off (`web/routes/auth.py` `build_router`).
  - Keep `ROLE_BOOTSTRAP` as the recovery path.
  - Optional later: core's planned JWT validation (`X-authentik-jwt`).
- [ ] Real Grafana panels once embedding is configured (`allow_embedding`, CSP/X-Frame-Options at Caddy; see the
  brief)

## Next from the greentechhub repos

Each waits on a gth release (planned in greentechhub-fastapi's TODO › M5 and greentechhub-ui's TODO), then is one
PR here: bump the pin, adopt, remove the item.

- [ ] `feat(web): CSRF on in-app forms`
  - **Why:** the sign-in form has CSRF, but `POST /logout`, `/settings`, `/admin/roles` and PyFinBot's own htmx
    forms (stocks, transactions, imports, syncs) don't.
  - **Waits on:** greentechhub-fastapi's planned `feat(auth): CSRF for htmx forms` and the ui app-shell change that
    sends the token in `hx-headers`.
  - **Then:** opt `register_settings`/`RoleAdminViews`/logout in and guard PyFinBot's POST/PUT/DELETE page routes.
- [ ] `feat(web): audit log`
  - **What:** record sign-ins, failed sign-ins, lockouts, role and settings changes (fastapi records these itself)
    plus PyFinBot's sync runs (market, dividends, email) and imports.
  - **Waits on:** greentechhub-fastapi's planned `register_audit`. Core's `gth_audit_log` table needs a migration
    here (`audit_log_table` on `SQLModel.metadata`, as with `gth_login_attempts`).
  - **Then:** show it as an activity feed with ui's planned `gth_timeline`.
- [ ] Charts on the reports — gains by FY, dividends over time — with greentechhub-ui's planned SVG charts (same
  wait as the dashboard)

### Leaner, once the gth repos ship them

Registered as "Leaner services" in greentechhub-core's TODO (C1–C7), greentechhub-fastapi's (F1–F6) and
greentechhub-ui's (U1–U3). Each is one PR here after its release: bump the pin, adopt, delete.

- [ ] Bearer API auth (fastapi F1): delete `core/security.py`, most of `core/dependencies.py` and
  `ACCESS_TOKEN_EXPIRE_MINUTES`. API routes take an `Identity` (`identity.subject`) instead of a `User`. This
  also ends the session cookie being accepted as an API token (same secret and HS256 today).
- [ ] Query errors (fastapi F2): delete `api/query.py`; use `PageParams.to_page_request` directly.
- [ ] Logging (fastapi F3): `register_logging(app, settings, service="pyfinbot", version=...)` replaces
  `pyfinbot.py`'s direct `configure_logging` call and the uvicorn re-routing.
- [ ] CSV export (fastapi F4): delete `web/csv_response.py` and `_plain` in `web/routes/transactions.py`.
- [ ] htmx helpers (fastapi F5): drop the 5 hand-set `HX-Trigger`s (`dividends.py`, `emails.py`, `imports.py`), and
  `_field_errors` in `transactions.py`.
- [ ] Settings basics (core C3): drop `ENVIRONMENT`, `LOCK_DIR` and the ephemeral `secret_key` from
  `core/settings.py`, and the dev CORS block in `pyfinbot.py`.
- [ ] Database (core C4): `db/session.py` becomes a few lines over core's `Database`.
- [ ] Sync locks (core C5): `held(lock, name, ttl)` replaces `market_sync.py`'s `sync_guard`.
- [ ] IMAP (core C6): core's `imap_settings` and `ImapReader` replace the generic half of `core/email_sync.py`
  and `core/email_accounts.py`; the Commsec sender criteria and parser stay.
- [ ] Tests (core C7, greentechhub-testing): `tests/conftest.py` keeps only PyFinBot's own fixtures (about 110
  lines go).
- [ ] Templates (ui U3): `gth_result_panel` for `_import_result.html`/`_sync_result.html`; `gth_filter_bar` and
  `gth_download_button` for the three report panes; `gth_form_actions` for the stock/transaction forms; the
  amount tone and `fy` filters (drop `templating.py`'s `fy`); `gth_stat_grid`.

## Waiting on a decision: user email addresses

`User` has no email address, so the gth features that need one are off: the profile section's email, password
reset, email verification, and notifications by email (`register_email` with core's `smtp_settings`,
`register_notifications` for sync results).

- **Decide first:** add `User.email` (a migration, collected at `/settings` › Profile, verified) or stay
  username-only.
- In-app notifications (`register_notifications` without email) don't need it. They could report sync results now
  if wanted.

## Known limitations (accepted, not bugs)

- Stateless JWT, 24h expiry, no refresh/revocation — a leaked token is valid
  up to 24h with no force-logout. Acceptable for personal-use scale; would
  need a blocklist or refresh tokens to harden (fastapi's "Sessions &
  devices" idea).
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
- Signing in needs HTTPS or `http://localhost`: the session and CSRF
  cookies are `Secure`, so a plain-HTTP LAN address can't sign in.
