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
