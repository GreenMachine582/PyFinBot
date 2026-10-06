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

## greentechhub adoption: core v0.11, fastapi v0.13, ui v0.15 (pinned)

> From a review on 2026-10-05: core v0.10–v0.11, fastapi v0.12–v0.13 and ui v0.15 shipped the pieces this section
> was waiting on, plus opt-in features PyFinBot can use as they are. One PR at a time, in this order.

- [ ] 6. `feat(auth): CSRF on the sign-in form` — `csrf = True` on `PyFinBotLoginViews` (ui v0.15 renders the field).
  Needs HTTPS, as the session cookie already does
- [ ] 7. `feat(auth): throttle API logins` — once greentechhub-fastapi ships `throttled_login`
  (greentechhub-fastapi#56): bump the pin, then `/api/auth/login` calls it with `core.login_throttle.LOGIN_THROTTLE`
  and `client_address(request)`, so a lockout on the sign-in form also covers the API. Check the password in its own
  short-lived session, not `Depends(get_session)`: the tests' per-test connection would roll the throttle's writes
  back with that session
- [ ] 8. `refactor(settings): adapter settings from GTHBaseSettings` — once core v0.12 and fastapi's reads that
  fall back to core's lowercase fields (the #56 rework) are released: drop `Settings`' own `AUTH_ADAPTER`,
  `CORS_ALLOWED_ORIGINS`, `TRUSTED_PROXIES`, `ROLE_BOOTSTRAP` and `ROLE_GROUPS` and use core's lowercase fields
  (`settings.auth_adapter` in `web/routes/auth.py`; `pyfinbot.py`'s CORS dev default sets `cors_allowed_origins`)

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
