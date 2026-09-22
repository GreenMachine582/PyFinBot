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
- [ ] Stocks + Transactions pages — `gth-table`/`gth-modal`/`gth-form`
- [ ] Import page — upload + `gth-toast`
- [ ] Emails + Dividends pages — manual sync triggers + `gth-toast`
- [ ] Reports page — holdings, capital gains, and dividend income
- [ ] Dashboard placeholder — `gth-stat-card`s + empty Grafana iframe slot
- [ ] Later: swap `AUTH_ADAPTER=forward_auth` once Authentik is live (needs
      `register_core`'s `TRUSTED_PROXIES` wired first); real Grafana panels
      once embedding is configured

## Known limitations (accepted, not bugs)

- `GET /users/` requires a valid token but returns every user unfiltered —
  no admin/RBAC system built; deliberate scope boundary.
- Stateless JWT, 24h expiry, no refresh/revocation — a leaked token is valid
  up to 24h with no force-logout. Acceptable for personal-use scale; would
  need a blocklist or refresh tokens to harden.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
