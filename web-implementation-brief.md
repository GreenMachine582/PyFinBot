# PyFinBot Web Interface — Implementation Brief (v3)

> **v2 change summary**: v1 scoped PyFinBot's web UI as a self-contained build (its own templates, its own JWT-cookie auth plumbing). v2 reframes it as the first (alongside BottleBot's retrofit) consumer of two new shared packages — `greentechhub-core` and `greentechhub-ui` — so PyFinBot doesn't reinvent auth/UI plumbing that BottleBot already half-built and every future service would build again.
>
> **v3 change summary**: v2 was written while `greentechhub-core`/`greentechhub-ui` were still design docs (the companion `*_Project_Plan.md` files it pointed to no longer exist — both packages are now real, versioned repos with their own README/TODO/docs). This pass corrects v2's §5 against the packages' actual current source: the auth adapter mechanism it described (`greentechhub_core.auth.local.LocalAuthAdapter`, an abstract `AuthAdapter`, shared CSRF middleware) doesn't exist under those names or in that package — the real, already-shipped mechanism lives in `greentechhub-fastapi` (`register_auth`, `Depends(get_current_user)`) built on `greentechhub-core`'s `identity` module. The underlying architecture (pluggable adapter, `local` now, `forward_auth`-via-Authentik later, config not code) is unchanged and confirmed sound — only names/locations and a few gaps (no CSRF middleware, no login template, two undocumented routers) are corrected. `greentechhub-fastapi/TODO.md` itself flagged this brief as needing exactly this follow-up.

## 1. Objective

PyFinBot currently ships as a FastAPI JSON API only (`/api/...`, JWT bearer auth, interactive docs at `/docs`). This brief scopes a browser-based front end so a user can log in, manage stocks and transactions, run imports, and view reports without hitting the API directly — built on the shared `greentechhub-core`/`greentechhub-ui` packages rather than as a one-off.

## 2. Current backend (as-is)

- **Stack**: FastAPI + Uvicorn, SQLModel/SQLAlchemy 2.0 (async), Alembic migrations, PostgreSQL (SQLite in tests).
- **Auth**: `OAuth2PasswordBearer` — `POST /api/auth/login` exchanges credentials for a JWT (`HS256`, 24h expiry, no refresh/revocation). Every route but registration and login requires `Authorization: Bearer <token>`.
- **Data model**: `User` (string PK) → `Transaction` (FK `user_id`, cascade delete) → `Stock` (FK `stock_id`, no cascade). `Transaction` carries computed fields (`total_value`, `cost`, `fy`) derived server-side on insert.
- **Routers**: `auth`, `users`, `stocks` (CRUD + market sync + `search`), `transactions` (CRUD, paginated via `fastapi-pagination`), `transactions/import` (CSV/Excel bulk import with row-level validation and dedupe), `emails` (`POST /api/emails/sync-commsec` — Gmail IMAP ingestion of Commsec buy/sell confirmation emails), `dividends` (`POST /api/dividends/sync` — yfinance dividend history sync), `reports` (holdings snapshot, FY capital gains, FY dividend income).
- **Known gaps** (from the project's own backlog): no RBAC, stateless JWT with no revocation — unsolved anywhere in the ecosystem yet, not PyFinBot-specific to fix. CORS/env-mode config now exists (`ENVIRONMENT`/`CORS_ORIGINS` in `core/settings.py`), built independently of `greentechhub-fastapi`'s equivalent `register_core` (see §10 for the resulting duplication to clean up).

## 3. Requested capabilities

- Auth login (against existing JWT endpoint)
- Create/edit forms for stocks and transactions
- Filterable, sortable, paginated tables (transactions, stocks, import results)
- Relational field mapping — transaction rows reference `stock_id`/`user_id`; forms and tables need to resolve these to human-readable symbol/name rather than raw FKs
- Popovers (inline help / row detail)
- Toast/notification messages for async actions
- Modal dialogs (create/edit forms, delete confirmation)
- Bootstrap 5 as the component/styling base
- A dashboard view

## 4. Architecture: consume, don't rebuild

**Stack: FastAPI + Jinja2 + HTMX + Alpine.js + Bootstrap 5 — supplied by `greentechhub-core` and `greentechhub-ui`, not implemented per-service.**

What v1 got right and v2 keeps: server-rendered, same-origin (no new CORS surface), no Node build chain, HTMX for the CRUD-heavy interactions. What changes: PyFinBot doesn't own the base layout, the component macros, the theme, the auth-cookie plumbing, health endpoints, or pagination/filter parsing — those come from the shared packages, the same way BottleBot's retrofit and any future service consume them.

**Addition over v1: Alpine.js** sits alongside HTMX — HTMX handles server round-trips (table filter/sort/pagination, form submits), Alpine handles pure client-side interaction (dropdowns, tabs, the dark-mode toggle, popover open state) without hand-written JS. Note: `greentechhub-ui`'s actual shipped dark-mode toggle (`gth_theme_toggle`, confirmed in its `TODO.md`) is vanilla JS, not Alpine — Alpine remains a reasonable choice for PyFinBot's own client-side bits, just not something to assume every `greentechhub-ui` interactive piece already uses it.

### What PyFinBot actually builds
```
src/pyfinbot/
├── web/
│   ├── routes/         # login, dashboard, stocks, transactions, import, reports
│   │                    # — business logic and route wiring only
│   └── templates/       # PyFinBot-specific pages only (extend greentechhub_ui base templates)
```
No `static/`, no base layout, no navbar/card/modal/toast macros — those are `import greentechhub_ui` and `import greentechhub_fastapi`, per the integration patterns documented in each package's own `docs/`.

## 5. Auth & session handling

v1 spent significant design effort on JWT-cookie handling and CSRF because it assumed PyFinBot would own that logic. It won't — but the owner is `greentechhub-fastapi`, not `greentechhub-core` as v2 claimed. Verified directly against current source (`greentechhub-fastapi/src/greentechhub_fastapi/{registration/auth.py,auth/local.py,auth/forward_auth.py,auth/cookies.py}` and `greentechhub-core/src/greentechhub_core/identity/{provider.py,models.py}`) — `greentechhub-core` has no `auth` module at all; auth-adjacent work there is filed under `identity` (the `IdentityProvider` protocol, `DevelopmentIdentityProvider`, `AuthentikIdentityProvider`) and `security` (a raw CSRF-token-generation primitive only). The real adapter-selection layer — what v2 called `LocalAuthAdapter`/`AuthAdapter` — is `greentechhub-fastapi`'s `register_auth`:

```python
# greentechhub_fastapi/registration/auth.py (real, current, shipped as of v0.5)
def register_auth(app: FastAPI, settings: GTHBaseSettings) -> None:
    adapter = read_str_setting(settings, "AUTH_ADAPTER", "local")
    if adapter == "local":
        provider = DevelopmentIdentityProvider(secret_key=settings.secret_key)
        app.dependency_overrides[get_current_user] = build_local_get_current_user(provider)
    elif adapter == "forward_auth":
        provider = AuthentikIdentityProvider()
        app.dependency_overrides[get_current_user] = build_forward_auth_get_current_user(provider)
```

- **Now**: `AUTH_ADAPTER=local` (the default) — `register_auth` builds a `DevelopmentIdentityProvider` and rebinds `Depends(get_current_user)` (from `greentechhub_fastapi.auth.dependency`) to resolve it from an httpOnly session cookie (`gth_session`, set via `greentechhub_fastapi.auth.cookies.create_session_cookie`). The provider verifies a **locally-issued JWT** (`DevelopmentIdentityProvider.issue(identity)`, HS256, signed with `settings.secret_key`) — not PyFinBot's existing bearer-token `/api/auth/login` flow directly. Concretely, PyFinBot has to write its own web login route: check credentials the same way `auth_routes.py` already does (`verify_password` against `User.password_hash`), build a `greentechhub_core.identity.Identity` (`subject=user.id`, `username=...`, `email=...`, `groups=[]`, `claims={}`), call `DevelopmentIdentityProvider(secret_key=settings.secret_key).issue(identity)`, then `create_session_cookie(response, token)`. The package deliberately ships **no login/logout routes itself** (`docs/auth.md`: *"they call a service's own credential-check logic... and use this module purely to set/clear the session cookie"*) — this is real route code PyFinBot writes, not glue. It runs **alongside**, not instead of, the existing bearer-token `POST /api/auth/login` (API clients are unaffected).
- **Later**: `AUTH_ADAPTER=forward_auth` — once Caddy fronts PyFinBot with an Authentik outpost (`goauthentik.io`, per `GreenMachine582/Homelab`), the adapter swap is a config change, and it's **already built and shipped** (v0.5, `AuthentikIdentityProvider` + `build_forward_auth_get_current_user`), not future work to be written when the time comes. One real prerequisite: `register_core` must also be called, with the Authentik outpost's address in `TRUSTED_PROXIES` — the forward-auth trust decision is made by `ProxyHeadersMiddleware` (which only `register_core` installs), exposed as `request.state.trusted_proxy`; skipping `register_core` doesn't create a security hole, it just fails closed (nothing ever resolves). Only the OIDC-token path (validating `X-authentik-jwt` against Authentik's JWKS) is still deferred upstream (`greentechhub-core` v0.5.1, needs a live Authentik instance) — the forward-auth *header* path PyFinBot would actually use is done.
- **SSO (GitHub/Google)**: unchanged from v2 — not PyFinBot's concern once Authentik is the IdP; social login is an Authentik-side federation setting.
- **CSRF — a real gap, not "handled elsewhere."** Neither package ships CSRF middleware. `greentechhub-core.security.tokens` only provides a raw token-generation/constant-time-comparison primitive; the session cookie's `samesite="lax"` (hardcoded in `auth/cookies.py`, not configurable) is the only baseline protection in place. If PyFinBot's HTMX form posts need more than that, it's this app's own work to add — don't assume it's provided.
- **No login page exists to reuse.** `greentechhub-ui` ships no `auth/login.html` or login component today (its `templates/`/`components/` directories have no such file — confirmed by listing both). §6 below reflects this: PyFinBot builds the whole login page, not just branding over a shared template.
- **A required settings change**: `register_auth`/`register_core` read `settings.secret_key` (lowercase) directly, and `greentechhub_core.config.GTHBaseSettings` (the base class every service's `Settings` is meant to extend) declares `secret_key: str` as a required field. PyFinBot's current `Settings.SECRET_KEY` is uppercase and auto-generates an ephemeral random default. Cleanest fix: have `Settings` extend `GTHBaseSettings` directly rather than `pydantic_settings.BaseSettings` — env-var matching is case-insensitive there, so the existing `SECRET_KEY` env var still resolves it, no `.env` changes needed.
- The one thing worth over-engineering slightly, carried over unchanged from v2: make sure no route handler imports anything from `greentechhub_fastapi.auth.local` or `.forward_auth` directly — only `Depends(get_current_user)`. That discipline is what makes the swap free.

## 6. Pages / views

| Page | Notes |
|---|---|
| Login | No shared template exists yet (`greentechhub-ui` has no `auth/login.html` — confirmed against current source). PyFinBot builds the page and posts to its own new session-cookie login route (§5), extending `greentechhub_ui`'s base `app.html` shell for branding/nav only |
| Dashboard | `gth-stat-card` summary tiles (holdings value, YTD gain/loss, total dividends received) + Grafana iframe placeholder (§8) |
| Stocks | `gth-table` (filter/sort on symbol, market, name, active status); `gth-modal` create/edit form; market sync action |
| Transactions | `gth-table` (filter by stock, type, date range, FY) + `gth-pagination`; `gth-modal` create/edit form; stock field is a searchable dropdown against `Stock.search`, not a raw ID input |
| Import | File upload (CSV/Excel), HTMX-submitted; result table with per-row validation errors; `gth-toast` on completion |
| Emails | Manual "Sync Commsec emails" trigger (`POST /api/emails/sync-commsec`) with a `gth-toast` result summary, mirroring BottleBot's manual scrape-trigger pattern — not in v2, added here since the router already exists |
| Dividends | Manual "Sync dividends" trigger (`POST /api/dividends/sync`, optional per-stock) + `gth-toast` — not in v2, added here since the router already exists |
| Reports | Holdings snapshot (as-of date picker), FY capital-gains report, and FY dividend-income report (`GET /api/reports/dividends`) — the last of these existed in the backend but was missing from v2's page list entirely — all `gth-table`, export-to-CSV |

## 7. Relational field mapping

- **Tables**: `gth-table` renders resolved relationships server-side (e.g. `AAPL · NASDAQ` instead of `stock_id=17`) — the API already exposes this via `Transaction.stock`, just needs to be in the template context.
- **Forms**: `gth-form`'s FK-field pattern is a searchable `<select>` (HTMX-powered, hitting `Stock.search` on keystroke) instead of a raw numeric input.
- `user_id` stays implicit — always the authenticated user, per the API's existing ownership model — never an editable field, consistent with how the API already derives it from the JWT rather than trusting client input.

## 8. Dashboarding (placeholder)

Homelab already runs Grafana (`homelab-observe` node, internal URL `http://grafana.homelab.local:3000`). Plan for now:

- Dashboard page embeds a Grafana panel/dashboard via `<iframe>`, pointed at a Grafana URL (panel ID + `kiosk` mode) — placeholder only until real panels exist.
- Dependencies to resolve before this works, not blocking initial build: Grafana `allow_embedding = true` and `X-Frame-Options`/CSP config (sits behind Caddy on the homelab edge); viewer auth for the embedded panel (Grafana anonymous viewer scoped to LAN/Tailscale now, or a shared Authentik OIDC session later so the iframe doesn't prompt separately); network reachability to `homelab-observe`.
- Until real panels exist, ship the dashboard with `gth-stat-card` summaries and an empty/"coming soon" iframe slot.

## 9. Ecosystem placeholders

- **Authentik as IdP**: covered in §5 — the adapter swap is designed in at the `greentechhub-fastapi`/`greentechhub-core` level (not re-solved per service), and the `forward_auth` side is already shipped, not just designed. Note `greentechhub-core`'s own README currently carries a "Status: Hold" badge — it's paused pending its adapter packages consuming it, which has already happened (`greentechhub-fastapi` is built on its `identity`/`config`/`security` modules today), so this isn't a blocker for PyFinBot, just worth knowing the upstream package considers itself between milestones.
- **Deployment target**: Homelab's `homelab-svc-02` node is earmarked for "user-facing application workloads" (currently "Planned"). Existing `Dockerfile`/`docker-compose.yml` should work as-is or with minor env additions once that node is active.
- **PyFinBot is not the only consumer**: BottleBot's existing FastAPI+HTMX+Bootstrap web UI is the retrofit case for both shared packages; PyFinBot is the greenfield case. Building both roughly in parallel is what actually validates the packages are reusable rather than PyFinBot-shaped.

## 10. Non-functional / cleanup items

- RBAC and JWT revocation remain unbuilt anywhere in the ecosystem today — not tracked as a blocking dependency, just not yet PyFinBot's to solve either.
- **CORS/env-mode is `greentechhub-fastapi`'s `register_core`, not `greentechhub-core`** (correcting v2, which named the wrong package): `register_core(app, settings)` wires request-ID, timing, security-header, CORS, and trusted-proxy middleware in one call, reading `CORS_ALLOWED_ORIGINS` (a list setting). This is a real, concrete duplication worth flagging: PyFinBot already built its own `CORS_ORIGINS`/`ENVIRONMENT` settings + manual `CORSMiddleware` registration independently (see `todo.md`) — the env var name doesn't even match (`CORS_ORIGINS` vs. `CORS_ALLOWED_ORIGINS`). Adopting `register_core` instead, at the same time as wiring `register_auth`, is a genuine follow-up consolidation — the same shape as BottleBot's `register_health` adoption — not just a nice-to-have. It's also a hard prerequisite for the `forward_auth` swap (§5): `register_core` is what installs `ProxyHeadersMiddleware` and reads `TRUSTED_PROXIES`.
- No behavior change to the existing `/api` — the web layer is additive.

## 11. Suggested phasing

v2 sequenced this against `greentechhub-core`/`greentechhub-ui`'s *planned* phasing ("wait for v0.1–v0.3"). Both packages have shipped real tagged releases since (`greentechhub-fastapi` v0.5.0, `greentechhub-ui` v0.6.0) — there's nothing left to wait for, so this is now a straight build sequence:

1. **Dependencies + registration**: pin `greentechhub-fastapi` and `greentechhub-ui` as `git+https://github.com/GreenMachine582/greentechhub-{fastapi,ui}.git@vX.Y.0` dependencies — this exact pattern was just proven end-to-end on BottleBot (built, tested, verified live), so start pinned rather than with local editable installs the way BottleBot originally did and later had to migrate off. Have `Settings` extend `GTHBaseSettings` (§5), add `AUTH_ADAPTER`, and call `register_core` + `register_auth` in `pyfinbot.py`.
2. **Login + base shell**: build PyFinBot's own login route (§5 — no shared template/adapter route exists to reuse) and base `web/templates/` extending `greentechhub_ui`'s `app.html`.
3. **Core CRUD**: Stocks and Transactions via `gth-table`/`gth-modal`/`gth-form`.
4. **Import**: upload page, `gth-toast` on completion.
5. **Emails + Dividends**: manual sync-trigger pages (§6) — small, since both are just a button + `gth-toast` over an existing endpoint.
6. **Reports**: holdings snapshot, capital-gains, and dividend-income views.
7. **Dashboard placeholder**: `gth-stat-card`s + empty Grafana iframe slot.
8. **Later**: swap `AUTH_ADAPTER` to `forward_auth` once Authentik is live (set `TRUSTED_PROXIES` via `register_core` first — see §5); wire real Grafana panels once embedding is configured.

## 12. Open decisions

Two of v2's three "open" decisions are effectively resolved now by precedent, not still open:

- ~~Pinned pre-1.0 vs. wait for v1.0~~ — **resolved**: pin now (§11). BottleBot already did exactly this today against these exact tagged versions and it works cleanly end-to-end; there's no longer a hypothetical to weigh.
- ~~Static asset hosting (bundled-per-service vs. shared `static.green-tech-hub.com`)~~ — **resolved**: bundled-per-service. BottleBot's actual implementation settled this in practice — `greentechhub_ui.static_path` mounted at `/gth-assets` via FastAPI's `StaticFiles`, no shared static host built or needed. PyFinBot should follow the same mount pattern.
- **Still genuinely open**: whether the web UI ships in the same FastAPI process/Dockerfile as the API, or as a separate service behind Caddy — recommend same process for now given single-user scale; no new information changes this call.
