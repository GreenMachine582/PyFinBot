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

Each is one PR on the current pins (core v0.16, fastapi v0.18, ui v0.20): adopt, remove the item.

- [ ] `refactor: gth upload reader`: greentechhub-fastapi's `uploads.read_upload(file, limit=)` (v0.18) replaces
  `core/transaction_import.read_upload`. The import page catches `UploadTooLargeError` to keep its form error; the
  API gets the 413 `payload_too_large` envelope.
- [ ] `refactor(cli): csv_text`: greentechhub-core's `exports.csv_text` / `csv_value` (v0.16) replace the hand-built
  `csv.writer` in `cli.py`'s report export, matching the web download (`csv_download`). Decide on `bom=False` for
  stdout.

## Waiting on a gth release

Nothing waiting. When an item needs a gth feature that isn't released yet, it goes here and is registered in
that repo's TODO; once it ships: bump the pin, adopt, remove the item.

## Waiting on infrastructure

- [ ] Switch to `AUTH_ADAPTER=forward_auth` once Authentik is live. The code side is ready:
  `register_core`/`register_auth`, core's `trusted_proxies`, and `register_users` (accounts are provisioned and
  linked by Authentik `uid` on first sign-in, with email and display name kept in step).
  - Set `AUTH_ADAPTER=forward_auth`, `TRUSTED_PROXIES` to the outpost's address, and `ROLE_GROUPS` (e.g.
    `admins=admin`).
  - In Authentik:
    - Add a SCIM provider (users only) pointed at `/scim/v2`, with `SCIM_TOKEN` set to the same token. Its
      `externalId` mapping must be the user's `uid`.
    - Add Google, GitHub and Apple as sources if wanted.
    - For Apple's private-relay addresses, register the sending domain with Apple.
  - The local sign-in routes switch themselves off (`web/routes/auth.py` `build_router`).
  - Keep `ROLE_BOOTSTRAP` (by username) as the recovery path.
  - Optional later: core's planned JWT validation (`X-authentik-jwt`).
- [ ] Real Grafana panels once embedding is configured (`allow_embedding`, CSP/X-Frame-Options at Caddy; see the
  brief). The dashboard side is ready: ui's `gth_embed_card`, and the strict CSP allows the Grafana origin in `frame-src`
  once `GRAFANA_ORIGIN` is set.

## Ideas — not scheduled

- htmx 2 through `shell_globals(htmx=2)`, ahead of ui's breaking switch (ui's CI already runs its e2e suite on it).
- One sync-result handler for the email, dividend and import routes (refuse when running, count, pick the toast
  tone, swap the badges panel). Stays here until a second service has the same shape.

## Known limitations (accepted, not bugs)

- The session cookie and `/api/auth/login`'s token are stateless JWTs (24h, no refresh or per-token revocation).
  Deactivating the account stops all of them at once, since every request reads the account, but a leaked token for
  an active account stays valid until it expires. Either works on pages and the API. Scripts should use a revocable
  personal API token instead (/settings › API tokens). Revoking one browser session would need fastapi's "Sessions &
  devices" idea. Acceptable at personal-use scale.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
- Signing in needs HTTPS or `http://localhost`: the session and CSRF
  cookies are `Secure`, so a plain-HTTP LAN address can't sign in.
