# PyFinBot TODO

Cross-session backlog — open work only. Finished items are removed rather
than ticked; `git log` (and each PR) is the history.

Every PR puts its tests in its own new test file and must pass `pytest`
(coverage ≥ 80), `ruff check src tests` and `mypy src/pyfinbot` (no errors).
Test web changes against the demo seed (`python scripts/seed_demo.py`).

When an item needs something the greentechhub repos don't have yet, add it
there first rather than hand-rolling it here. Framework-free pieces go in
core, then fastapi, then ui. Each is released in that order before this repo
bumps its pins in `requirements.txt`. Develop across the repos with local GTH
mode (`scripts/use-local-gth.sh`, see CONTRIBUTING.md); CI always tests the
pins.

Web UI scope and architecture: see `web-implementation-brief.md`.

## Ready now — released in the gth repos

One PR each, in this order. `requirements.txt` already pins core v0.14, fastapi v0.16 and ui v0.17.

- [ ] `refactor(web): gth ui macros` (ui v0.16)
  - `gth_result_panel` for `_import_result.html`/`_sync_result.html`.
  - `gth_filter_bar` and `gth_download_button` for the three report panes.
  - `gth_form_actions` (or `gth_modal_form`) for the stock/transaction forms.
  - The `tone` and `fy` filters and `gth_amount`; drop `templating.py`'s own `fy` filter.
  - `gth_stat_grid` for the dashboard's stat tiles.
- [ ] `feat(web): CSRF on in-app forms` (fastapi v0.16, ui v0.17)
  - **Why:** the sign-in form has CSRF, but `POST /logout`, `/settings`, `/admin/roles` and PyFinBot's own htmx
    forms (stocks, transactions, imports, syncs) don't.
  - `register_csrf(app)` (fastapi docs/auth.md); ui v0.17's shell sends the token in `hx-headers`.
  - Opt `register_settings`/`RoleAdminViews`/logout in and guard PyFinBot's POST/PUT/DELETE page routes.
- [ ] `feat(web): audit log` (fastapi v0.16, ui v0.17)
  - Record sign-ins, failed sign-ins, lockouts, role and settings changes (fastapi records these itself) plus
    PyFinBot's sync runs (market, dividends, email) and imports.
  - `register_audit(app, settings, store=..., views=AuditViews(...))` (fastapi docs/registration.md) with ui's
    audit log page. Core's `gth_audit_log` table needs a migration here (`audit_log_table` on
    `SQLModel.metadata`, as with `gth_login_attempts`).
  - The activity feed is its own item below.
- [ ] `feat(web): dashboard and report charts` (ui v0.17)
  - **Dashboard:** sparklines in the stat tiles (cost base over time, dividends by month) with `gth_sparkline` in
    `gth_stat_card` (`web/routes/dashboard.py`).
  - **Reports:** gains by FY (`gth_bar_chart`), dividends over time (`gth_line_chart`).
  - The Grafana panel is under infrastructure.

## Waiting on a gth release

Each is one PR here once it ships: bump the pin, adopt, remove the item. Each is registered in that repo's TODO.

- [ ] `feat(web): strict CSP`
  - **Waits on:** greentechhub-fastapi M6 `register_csp` (ui v0.17's shell is already CSP-ready).
  - **Then:** turn it on with a `frame-src` for the Grafana origin.
- [ ] `feat(web): Admin nav group`
  - **Waits on:** greentechhub-fastapi M6 `register_admin`.
  - **Then:** Roles and Audit log under "Admin", shown to admins only.
- [ ] `feat(api): personal API tokens`
  - **Waits on:** greentechhub-core's API token store and greentechhub-fastapi M6 personal API tokens.
  - **Then:** scripts use a revocable personal token instead of a 24h login JWT (see Known limitations).
- [ ] `feat(web): audit activity feed`
  - **Waits on:** greentechhub-ui M6 `gth_timeline`, and the audit log item above.
  - **Then:** the audit entries as a feed (dashboard or its own page).
- [ ] `feat(web): HTML error pages`
  - **Why:** pages get FastAPI's default JSON errors (`pyfinbot.py`'s handlers cover `/api` only).
  - **Waits on:** greentechhub-fastapi M6 `register_error_pages` (ui v0.17's 403/404/500 templates).
- [ ] `refactor(web): leaner routes` — one step per gth helper as it ships:
  - greentechhub-fastapi `get_owned_or_404` replaces `_get_stock_or_404`/`_get_transaction_or_404`;
  - greentechhub-core's `held_lock` and per-user lock name replace `sync_guard` (`core/market_sync.py`) and
    `email_sync_lock`;
  - greentechhub-core's `GTHBaseSettings` `retired=` replaces `_warn_retired` (`core/settings.py`);
  - greentechhub-ui's `pluralise` filter replaces `_plural` (`web/routes/imports.py`) and the inline plurals in
    the email and dividend sync handlers.

## Waiting on infrastructure

- [ ] Switch to `AUTH_ADAPTER=forward_auth` once Authentik is live. The code side is ready:
  `register_core`/`register_auth`, and core's `trusted_proxies`.
  - Set `AUTH_ADAPTER=forward_auth`, `TRUSTED_PROXIES` to the outpost's address, and `ROLE_GROUPS` (e.g.
    `admins=admin`).
  - The local sign-in routes switch themselves off (`web/routes/auth.py` `build_router`).
  - Keep `ROLE_BOOTSTRAP` as the recovery path.
  - Optional later: core's planned JWT validation (`X-authentik-jwt`).
- [ ] Real Grafana panels once embedding is configured (`allow_embedding`, CSP/X-Frame-Options at Caddy; see the
  brief). The dashboard side is ready: ui v0.17's `gth_embed_card`, with the strict CSP item's `frame-src`.

## Ideas — not scheduled

- htmx 2 through `shell_globals(htmx=2)`, ahead of ui's breaking switch (ui's CI already runs its e2e suite on it).
- One sync-result handler for the email, dividend and import routes (refuse when running, count, pick the toast
  tone, swap the badges panel). Stays here until a second service has the same shape.

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
  up to 24h with no force-logout, even after its user is deleted (nothing
  looks the user up). An API token and the session cookie are the same kind
  of JWT, so either works on pages and the API. Acceptable for personal-use
  scale.
  Scripts move to revocable personal tokens (the personal API tokens item);
  browser sessions would need fastapi's "Sessions & devices" idea.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
- Signing in needs HTTPS or `http://localhost`: the session and CSRF
  cookies are `Secure`, so a plain-HTTP LAN address can't sign in.
