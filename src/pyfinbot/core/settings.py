
import os
import secrets
import tempfile
import warnings
from os import path as os_path

from dotenv import load_dotenv
from greentechhub_core.config import GTHBaseSettings


load_dotenv(dotenv_path=os_path.join(os_path.dirname(__file__), "..", "..", "..", ".env"))


class Settings(GTHBaseSettings):
    ASYNC_DATABASE_URL: str = ""
    DATABASE_URL: str = ""
    DB_ECHO: bool = False

    # JWT signing secret. Defaults to a fresh random value each process start
    # (so tokens issued before a restart become invalid) unless overridden via
    # the environment/.env — set this explicitly in any persistent deployment.
    # Overrides GTHBaseSettings' own secret_key (which has no default and
    # would otherwise be a hard validation error at import time when unset)
    # to keep that ephemeral-fallback behavior. Env var stays SECRET_KEY —
    # GTHBaseSettings matches env vars case-insensitively.
    secret_key: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # AUTH_ADAPTER for greentechhub_fastapi.register_auth: "local" (default,
    # a locally-issued session JWT) or "forward_auth" (Authentik outpost —
    # not wired up yet, deferred).
    AUTH_ADAPTER: str = "local"

    # Gmail IMAP (App Password auth, not OAuth) for Commsec email ingestion.
    # An App Password is broader-scoped than a typical API credential (full
    # mailbox read access) — recommend a dedicated Gmail label/account.
    GMAIL_ADDRESS: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GMAIL_IMAP_HOST: str = "imap.gmail.com"
    GMAIL_IMAP_PORT: int = 993
    GMAIL_MAILBOX: str = "INBOX"
    COMMSEC_SENDER: str = "bounceback@commsec.com.au"

    # "development" or "production". Controls the CORS default in pyfinbot.py:
    # development allows all origins when CORS_ALLOWED_ORIGINS is unset
    # (frictionless local/Swagger testing); production allows none until
    # CORS_ALLOWED_ORIGINS is set. Read by greentechhub_fastapi.register_core
    # (via its own tolerant read_list_setting, which has no such dev-mode
    # default — the "*" fallback is applied in pyfinbot.py, not here).
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: str = ""

    # Directory for greentechhub_core FileLock files (e.g. the market-sync
    # "already running" guard). Must be shared by every worker/replica on the
    # host for the lock to span them; the default is fine for one container.
    LOCK_DIR: str = os_path.join(tempfile.gettempdir(), "pyfinbot-locks")

settings = Settings()

if not settings.secret_key:
    settings.secret_key = secrets.token_hex(32)
    if not os.environ.get("SECRET_KEY"):
        warnings.warn(
            "SECRET_KEY is not set in the environment/.env — using a random "
            "ephemeral key for this process. All issued tokens will become "
            "invalid on restart. Set SECRET_KEY explicitly for any deployment "
            "that needs to survive a restart.",
            stacklevel=2,
        )

if settings.ENVIRONMENT == "production" and not settings.CORS_ALLOWED_ORIGINS:
    warnings.warn(
        "ENVIRONMENT is 'production' but CORS_ALLOWED_ORIGINS is not set — no "
        "cross-origin requests will be allowed until CORS_ALLOWED_ORIGINS is "
        "set to an explicit comma-separated allow-list.",
        stacklevel=2,
    )
