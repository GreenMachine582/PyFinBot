from greentechhub_fastapi.dependencies import require_page_identity

# Web-page auth guard: the logged-in Identity, or a bounce to /login (303,
# or HX-Redirect for HTMX requests) — see greentechhub-fastapi docs/auth.md.
page_identity = require_page_identity(login_url="/login")
