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

Nothing ready: every released gth feature is adopted. The items below wait on a gth release or
infrastructure.

## Waiting on a gth release

Each is one PR here once it ships: bump the pin, adopt, remove the item. Each is registered in that repo's TODO.

- [ ] `feat(web): audit activity feed`
  - **Waits on:** greentechhub-ui M6 `gth_timeline`, and the audit log item above.
  - **Then:** the audit entries as a feed (dashboard or its own page).
- [ ] `refactor(web): leaner routes`: what's left, one step per gth helper as it ships:
  - `_get_transaction_or_404` → greentechhub-fastapi's `get_owned_or_404` once it takes `options=` (passed to
    `session.get`), so `transaction.stock` can stay eager-loaded. The delete modal and route read it, and a lazy
    load fails under async. `_get_stock_or_404` already moved;
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
  brief). The dashboard side is ready: ui's `gth_embed_card`, and the strict CSP allows the Grafana origin in `frame-src`
  once `GRAFANA_ORIGIN` is set.

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

- The session cookie and `/api/auth/login`'s token are stateless JWTs (24h, no refresh or revocation): a leaked
  one is valid up to 24h with no force-logout, even after its user is deleted (nothing looks the user up). Either
  works on pages and the API. Scripts should use a revocable personal API token instead (/settings › API tokens).
  Browser sessions would need fastapi's "Sessions & devices" idea. Acceptable at personal-use scale.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
- Signing in needs HTTPS or `http://localhost`: the session and CSRF
  cookies are `Secure`, so a plain-HTTP LAN address can't sign in.
