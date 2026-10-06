
import os
import secrets
import tempfile
import warnings
from os import path as os_path


from dotenv import load_dotenv
from greentechhub_core.config import GTHBaseSettings
from pydantic_settings import SettingsConfigDict


load_dotenv(dotenv_path=os_path.join(os_path.dirname(__file__), "..", "..", "..", ".env"))


class Settings(GTHBaseSettings):
    # Ignore unknown keys rather than refuse to start, so an older .env
    # (e.g. the retired GMAIL_* settings) still loads; see _warn_retired.
    model_config = SettingsConfigDict(**{**GTHBaseSettings.model_config, "extra": "ignore"})

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

    # Roles (greentechhub-fastapi's register_permissions reads these):
    # ROLE_BOOTSTRAP maps user ids to roles — the first admin, and recovery if
    # every admin grant is removed, e.g. "alice=admin". ROLE_GROUPS maps
    # directory groups to roles (forward_auth/Authentik), e.g. "admins=admin".
    # Roles assigned at /admin/roles are stored in gth_role_grants instead.
    ROLE_BOOTSTRAP: str = ""
    ROLE_GROUPS: str = ""

    # SETTINGS_CIPHER_KEY, the Fernet key that encrypts secret settings at rest
    # (each user's email app password, in gth_settings), is greentechhub-core's
    # GTHBaseSettings.settings_cipher_key; pyfinbot.py builds the cipher with
    # core's settings_cipher, which derives one from secret_key when it's unset.

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

RETIRED_SETTINGS = ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "GMAIL_IMAP_HOST", "GMAIL_IMAP_PORT",
                    "GMAIL_MAILBOX", "COMMSEC_SENDER")


def _warn_retired(environ=os.environ) -> list[str]:
    """Warn about server-wide email settings that are set but no longer read
    (each user's email account now lives in their Settings). Returns them."""
    found = [name for name in RETIRED_SETTINGS if environ.get(name)]
    if found:
        warnings.warn(
            f"{', '.join(found)} {'is' if len(found) == 1 else 'are'} no longer used: each user "
            "sets their own email account at /settings › Email sync. Remove them from the "
            "environment/.env.",
            stacklevel=2,
        )
    return found


_warn_retired()


if settings.ENVIRONMENT == "production" and not settings.CORS_ALLOWED_ORIGINS:
    warnings.warn(
        "ENVIRONMENT is 'production' but CORS_ALLOWED_ORIGINS is not set — no "
        "cross-origin requests will be allowed until CORS_ALLOWED_ORIGINS is "
        "set to an explicit comma-separated allow-list.",
        stacklevel=2,
    )
