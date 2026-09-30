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
- [x] Stocks + Transactions pages — `gth_data_table` (sortable headers,
      `gth_table_filter`, load-more paging, refreshed on change), modal
      create/edit/delete, ASX sync action with titled toasts, `gth_badge`
      status/type pills, searchable stock picker; transactions are fully
      editable (derived fields recomputed via `Transaction.recompute()`, which
      `PUT /api/transactions/{id}` now uses too); covered by
      `tests/test_web_stocks.py`/`test_web_transactions.py`
- [x] Import page — upload + `gth-toast` — done: `/import` posts the file
      over HTMX and swaps in a result card (row/imported/skipped badges, a
      Row/Problem table for skipped rows) with a success/warning/danger toast
      that also fires `transactionsChanged`; the import itself moved to
      `core/transaction_import.py`, shared with `POST /api/transactions/import`
      (which also returns structured `row_errors` now); covered by
      `tests/test_web_import.py`
- [x] Emails + Dividends pages — manual sync triggers + `gth-toast` — done:
      `/emails` (Sync Commsec emails, with a not-configured hint) and
      `/dividends` (sync all my stocks, or one picked stock) swap in a result
      card with badges + a problems list and a toast; each sync takes a
      `sync_guard` lock so a double-click can't run two at once. The logic
      moved to `core/commsec_import.py` / `dividend_sync.user_stock_ids`,
      shared with the API routes; covered by `tests/test_web_emails.py` /
      `test_web_dividends.py`
- [x] Reports page — holdings, capital gains, and dividend income — done:
      `/reports` with lazy `gth_tabs` panes (holdings as-of date, capital
      gains by FY, dividend income by FY or all time), `gth_stat_card`
      totals + tables, and a CSV download per report for its current
      filter; the computations moved to `core/reports.py`, shared with
      `/api/reports/*`; covered by `tests/test_web_reports.py`
- [ ] Dashboard placeholder — `gth-stat-card`s + empty Grafana iframe slot
- [ ] Later: swap `AUTH_ADAPTER=forward_auth` once Authentik is live (needs
      `register_core`'s `TRUSTED_PROXIES` wired first); real Grafana panels
      once embedding is configured

## greentechhub-ui v0.11.0 adoption

v0.11.0 (the Data & forms release) adds date range presets, file drop, bulk
selection, column view options, CSV export URLs, form-field extras and shared
`money`/`number`/`date` filters. One PR per item, in this order (item 1 first:
the rest need the pin). Each PR puts its tests in its own new test file, and
must pass `pytest` (coverage ≥ 80), `ruff check src tests` and
`mypy src/pyfinbot`.

- [ ] `build(deps): greentechhub-ui v0.11.0; shared formatting filters` —
      pin `@v0.11.0` in `requirements.txt` and reinstall the local `.venv`
      (it currently has gth-ui **0.6.0**, not the pinned 0.10.0). Drop
      `_money`/`_qty` from `web/templating.py` (keep `_fy`; gth has no FY
      filter) — `install()` supplies `money`/`number`/`date`, and our own
      assignments after it would shadow them. `|qty` and `|string|qty` →
      `|number` (it takes the report schemas' floats directly). `|money` call
      sites stay but now print `$` (`-$264.95` for a buy's cost); per-unit
      prices (Price, Per share) stay `|number` so they keep full precision.
      Raw dates → `|date` ("5 Feb 2025"): the transaction table's
      `strftime("%d/%m/%Y")`, ex/pay dates in `_report_dividends.html`, the
      holdings empty state (keep the ISO `as_of` for input values and CSV
      hrefs). Update `test_web_reports.py:88,152` for the new date format
- [ ] `feat(transactions): date range presets` — `gth_date_range` replaces
      `transactions.html`'s hand-built From/To inputs (`hide_label=True`,
      `field_class="mb-0"`, `fy_start_month=7` default); same
      `date_from`/`date_to` params, so the route is unchanged. Keep the FY
      select
- [ ] `feat(import): drag-and-drop upload with a 5 MB limit` —
      `gth_file_drop("file", "File", accept=ACCEPTED_EXTENSIONS,
      max_size=MAX_UPLOAD_BYTES)` in `import.html` (the form already has
      `hx-encoding`); `MAX_UPLOAD_BYTES = 5 * 1024 * 1024` in
      `core/transaction_import.py`; `imports.py` reads at most limit + 1 bytes
      and raises `ImportFileError("File is larger than 5 MB.")` — the existing
      422 result panel + toast. Update `test_web_import.py:42`'s `accept`
      assertion
- [ ] `feat(transactions): CSV export and column view options` — split
      `_query_transactions` into a statement builder + paging so a new
      `GET /transactions.csv` takes the table's filters and sort with no paging
      (the `reports.py` CSV pattern; `pyfinbot-transactions.csv`: Date, Market,
      Symbol, Type, Units, Price, Fees, Total, Cost, FY, Notes; user-scoped);
      `export_base_url="/transactions.csv"` on `_table_state`. The 11-column
      table gets `view_options=True`: Date and Stock `hideable: False`, Notes
      `hidden: True`
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
- [ ] `feat(transactions): bulk delete` — **after the CSV export item** (same
      route and table files). `POST /transactions/bulk-delete` reads `ids` and
      deletes only the current user's rows (a user-scoped query, so another
      user's ids are silently ignored, like the 404-not-403 single delete);
      toast "Deleted N transactions" + `transactionsChanged`. The table gets
      `bulk_actions=[{"label": "Delete", "style": "btn-outline-danger",
      "confirm": "Delete the selected transactions?", ...}]` + select cells

## Known limitations (accepted, not bugs)

- `GET /users/` requires a valid token but returns every user unfiltered —
  no admin/RBAC system built; deliberate scope boundary.
- Stateless JWT, 24h expiry, no refresh/revocation — a leaked token is valid
  up to 24h with no force-logout. Acceptable for personal-use scale; would
  need a blocklist or refresh tokens to harden.
- `SECRET_KEY` auto-generates a random value each process start if unset
  (never a hardcoded/empty fallback) — a deployment that needs tokens to
  survive a restart must set it explicitly.
