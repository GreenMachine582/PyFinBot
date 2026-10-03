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

## greentechhub adoption: ui v0.14, core v0.9, fastapi v0.11 (slimming PyFinBot)

> From a review of PyFinBot's web layer (2026-10-03): hand-rolled pieces that belong in the gth repos moved there
> (opt-in), and PyFinBot drops its copies. One PR at a time, in this order.

Waiting on a gth release:
- [ ] greentechhub-ui, unreleased — `gth_select`/`gth_form_field` `id=` element-id prefix (#71)

PyFinBot, in order:
- [ ] 3a. `refactor(reports): FY selects as gth_select` — after a greentechhub-ui release with `gth_select(id=)` /
  `gth_form_field(id=)` (greentechhub-ui #71, not released yet): pin it, then
  `gth_select("fy", "Financial year", fys|fy_options, value=report.fy, id="gains-fy", field_class="mb-0")` in
  `_report_gains.html` and the same with `placeholder="All time"`, `id="dividends-fy"` in `_report_dividends.html`.
  Both are `name="fy"` in report panes that stay in the DOM, so without `id=` they'd share `id="gth-field-fy"`
- [ ] 6. `refactor(query): core's where / order_by / page` — the web tables use `order_by` + `paginate` (deleting
  `web/paging.py` and `core/sorting.py`); the API list routes use `PageParams` / `parse_filter_json` + `page()`
  (deleting `core/sa_filters_compat.py`). Check whether anything still sends the Tabulator `sorters` JSON: convert it
  to `Sort`s, or drop it if nothing does
- [ ] 7. `refactor(core): core's fiscal years` — `greentechhub_core.dates` replaces `core/fiscal_year.py`; the `|fy`
  filter uses `fiscal_year_label`
- [ ] 8. `refactor(core): core's password hashing` — `greentechhub_core.security.passwords` replaces the bcrypt
  helpers in `core/security.py`; same bcrypt format, so existing hashes still verify (test it)

The remaining greentechhub-ui v0.11.0 items below follow these.

## greentechhub-ui v0.11.0 adoption (remaining)

v0.11.0 (the Data & forms release) is already pinned (now v0.14). One PR per item, in this order.

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
- [ ] `feat(transactions): bulk delete` — `POST /transactions/bulk-delete` reads `ids` and
      deletes only the current user's rows (a user-scoped query, so another
      user's ids are silently ignored, like the 404-not-403 single delete);
      toast "Deleted N transactions" + `transactionsChanged`. The table gets
      `bulk_actions=[{"label": "Delete", "style": "btn-outline-danger",
      "confirm": "Delete the selected transactions?", ...}]` + select cells

## Known limitations (accepted, not bugs)

- Stateless JWT, 24h expiry, no refresh/revocation — a leaked token is valid
  up to 24h with no force-logout. Acceptable for personal-use scale; would
  need a blocklist or refresh tokens to harden.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
