from fastapi import Depends
from greentechhub_fastapi.auth.csrf import require_csrf
from greentechhub_fastapi.dependencies import require_page_identity

# Web-page auth guard: the logged-in Identity, or a bounce to /login (303,
# or HX-Redirect for HTMX requests) — see greentechhub-fastapi docs/auth.md.
page_identity = require_page_identity(login_url="/login")

# A page router's dependencies: signed in first (so an anonymous POST still
# gets the login redirect, not a 403), then a CSRF token on anything but
# GET/HEAD/OPTIONS. ui's app shell sends it on every htmx request
# (X-CSRF-Token, through hx-headers); every PyFinBot form posts through htmx.
page_router_deps = [Depends(page_identity), Depends(require_csrf)]
