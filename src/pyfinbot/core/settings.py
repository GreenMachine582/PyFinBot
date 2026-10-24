
import tempfile
from os import path as os_path
from typing import ClassVar


from dotenv import load_dotenv
from greentechhub_core.config import GTHBaseSettings
from pydantic_settings import SettingsConfigDict


load_dotenv(dotenv_path=os_path.join(os_path.dirname(__file__), "..", "..", "..", ".env"))


_EMAIL_MOVED = "each user sets their own email account at /settings › Email sync"
_TOKEN_LIFETIME_FIXED = "API tokens last 24 hours (api/auth_routes.py API_TOKEN_LIFETIME)"


class Settings(GTHBaseSettings):
    # Ignore unknown keys rather than refuse to start, so an older .env still
    # loads whatever it holds.
    model_config = SettingsConfigDict(**{**GTHBaseSettings.model_config, "extra": "ignore"})

    # Settings that still load when set but are no longer read, and why:
    # core warns once per reason at startup (GTHBaseSettings.retired).
    retired: ClassVar[dict[str, str]] = {
        "GMAIL_ADDRESS": _EMAIL_MOVED,
        "GMAIL_APP_PASSWORD": _EMAIL_MOVED,
        "GMAIL_IMAP_HOST": _EMAIL_MOVED,
        "GMAIL_IMAP_PORT": _EMAIL_MOVED,
        "GMAIL_MAILBOX": _EMAIL_MOVED,
        "COMMSEC_SENDER": _EMAIL_MOVED,
        "ACCESS_TOKEN_EXPIRE_MINUTES": _TOKEN_LIFETIME_FIXED,
    }

    ASYNC_DATABASE_URL: str = ""
    DATABASE_URL: str = ""
    DB_ECHO: bool = False

    # SECRET_KEY (core's secret_key) signs the session cookie and API tokens.
    # Unset, core fills a fresh random key for this process and warns, so
    # tokens issued before a restart stop working: set it in any persistent
    # deployment.
    ephemeral_secret_key: ClassVar[bool] = True

    # The adapter settings greentechhub-fastapi reads are greentechhub-core's
    # GTHBaseSettings fields (env vars in brackets), not declared here:
    #   auth_adapter (AUTH_ADAPTER): "local" (default, a locally-issued
    #     session JWT) or "forward_auth" (Authentik outpost — deferred).
    #   role_bootstrap (ROLE_BOOTSTRAP): user ids → roles, the first admin and
    #     recovery if every admin grant is removed, e.g. "alice=admin".
    #   role_groups (ROLE_GROUPS): directory groups → roles (forward_auth),
    #     e.g. "admins=admin". Roles assigned at /admin/roles are stored in
    #     gth_role_grants instead.
    #   cors_allowed_origins (CORS_ALLOWED_ORIGINS): see environment below.
    #   trusted_proxies (TRUSTED_PROXIES): the reverse proxy's address(es)
    #     (e.g. Caddy), so register_core takes the client IP from
    #     X-Forwarded-For; unset, every request has the proxy's address and
    #     the login throttle's per-client count is one count for everybody.

    # SETTINGS_CIPHER_KEY, the Fernet key that encrypts secret settings at rest
    # (each user's email app password, in gth_settings), is greentechhub-core's
    # GTHBaseSettings.settings_cipher_key; pyfinbot.py builds the cipher with
    # core's settings_cipher, which derives one from secret_key when it's unset.

    # environment (ENVIRONMENT), core's: "development" (the default) or
    # "production". With cors_allow_all_in_development, development allows all
    # origins when CORS_ALLOWED_ORIGINS is unset (frictionless local/Swagger
    # testing), and production allows none until it's set, with a warning.
    cors_allow_all_in_development: ClassVar[bool] = True

    # Where greentechhub_core FileLocks live (core's lock_dir, LOCK_DIR; read
    # through lock_directory()), e.g. the market-sync "already running" guard.
    # Every worker/replica on the host must share it for a lock to span them.
    # PyFinBot's own directory rather than core's shared gth-locks default, so
    # its lock names ("dividend-sync") can't meet another gth service's.
    lock_dir: str = os_path.join(tempfile.gettempdir(), "pyfinbot-locks")

    # The Grafana origin (e.g. "https://grafana.example.com") whose panels the
    # dashboard embeds in gth_embed_card frames: added to the strict
    # Content-Security-Policy's frame-src (register_csp in pyfinbot.py). Unset,
    # frames are same-origin only.
    GRAFANA_ORIGIN: str = ""

    # How long gth_audit_log keeps an entry: older ones are pruned on startup
    # (pyfinbot.py prune_audit_log). 0 keeps everything.
    AUDIT_RETENTION_DAYS: int = 365

    # The address people reach PyFinBot at (e.g. "https://pyfinbot.example"),
    # which makes the links in emails absolute: password reset, email
    # confirmation and notices (register_email in pyfinbot.py). Unset, those
    # emails carry relative links, so set it wherever email is set up.
    BASE_URL: str = ""

    # The bearer token Authentik's SCIM provider sends to /scim/v2 (a long
    # random secret, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
    # Set, register_scim mounts the endpoint so Authentik pushes account
    # changes (renames, new addresses, deactivations) the moment they happen;
    # unset, there's no /scim/v2 and changes arrive at the next sign-in.
    SCIM_TOKEN: str = ""


settings = Settings()
