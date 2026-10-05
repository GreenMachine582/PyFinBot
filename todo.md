# PyFinBot TODO

Cross-session backlog — open work only. Finished items are removed rather
than ticked; `git log` (and each PR) is the history.

Every PR puts its tests in its own new test file and must pass `pytest`
(coverage ≥ 80), `ruff check src tests` and `mypy src/pyfinbot` (≤ 55 errors).
Test web changes against the demo seed (`python scripts/seed_demo.py`).

## Open items

- [ ] Make mypy blocking in CI — currently advisory (`continue-on-error:
      true`); needs targeted `# type: ignore`s at ~21 known SQLModel/
      SQLAlchemy-typing-friction call sites, or better upstream SQLModel stubs
- [ ] FIFO Method Support — accurate gain/loss computation using FIFO (and
      per-parcel tracking), as an alternative/addition to the current
      average-cost-basis capital-gains calculation
- [ ] CLI Interface — interact via command line with exportable summaries

## Web UI (greentechhub-fastapi / greentechhub-ui)

Scope and architecture: see `web-implementation-brief.md`.

- [ ] Dashboard placeholder — `gth-stat-card`s + empty Grafana iframe slot
- [ ] Later: swap `AUTH_ADAPTER=forward_auth` once Authentik is live (needs
      `register_core`'s `TRUSTED_PROXIES` wired first); real Grafana panels
      once embedding is configured

## greentechhub adoption: core v0.11, fastapi v0.13, ui v0.15

> From a review on 2026-10-05: core v0.10–v0.11, fastapi v0.12–v0.13 and ui v0.15 shipped the pieces this section
> was waiting on, plus opt-in features PyFinBot can use as they are. One PR at a time, in this order.

- [ ] 1. `build(deps): core v0.11.0, fastapi v0.13.0, ui v0.15.0` (ui v0.16.0 if it's out by then). Brings core's
  `paginate` without SQLModel's `execute()` DeprecationWarning (every web table page and API list logs two today)
  with no code change. Check the alembic baseline still matches: none of the new gth tables is used yet
- [ ] 2. `refactor(settings): core's settings_cipher` — drop `core/settings.py`'s `settings_cipher_key` and the
  `SETTINGS_CIPHER_KEY` field (core's `GTHBaseSettings` has `settings_cipher_key` now) and pass
  `cipher=settings_cipher(settings, context="pyfinbot-settings")`. Same derivation, so saved app passwords stay
  readable; keep a test that a value encrypted the old way still decrypts
- [ ] 3. `refactor(reports): FY selects as gth_select` — `gth_select("fy", "Financial year", fys|fy_options,
  value=report.fy, id="gains-fy", field_class="mb-0")` in `_report_gains.html` and the same with
  `placeholder="All time"`, `id="dividends-fy"` in `_report_dividends.html`. Both are `name="fy"` in report panes
  that stay in the DOM, so without `id=` they'd share `id="gth-field-fy"`
- [ ] 4. `feat(settings): change password` — `SettingsViews(change_password=...)`: verify the current password
  against `User.password_hash` (core's `verify_password`) and store the new hash (`hash_password`)
- [ ] 5. `feat(auth): login throttling` — `throttle=LoginThrottle(SQLAlchemyAttemptStore(...))` on
  `PyFinBotLoginViews`, with an alembic migration for core's `gth_login_attempts` table (`login_attempts_table`)
- [ ] 6. `feat(auth): CSRF on the sign-in form` — `csrf = True` on `PyFinBotLoginViews` (ui v0.15 renders the field).
  Needs HTTPS, as the session cookie already does

Later, once `User` has an email address (a decision first): the profile section, password reset, email
verification and notifications (`register_email` with core's `smtp_settings`, `register_notifications` for sync
results).

## Known limitations (accepted, not bugs)

- Stateless JWT, 24h expiry, no refresh/revocation — a leaked token is valid
  up to 24h with no force-logout. Acceptable for personal-use scale; would
  need a blocklist or refresh tokens to harden.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
