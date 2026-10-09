
import os
import tempfile
import warnings
from os import path as os_path
from typing import ClassVar


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

    # SECRET_KEY (core's secret_key) signs the session cookie and API tokens.
    # Unset, core fills a fresh random key for this process and warns, so
    # tokens issued before a restart stop working: set it in any persistent
    # deployment.
    ephemeral_secret_key: ClassVar[bool] = True
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

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


settings = Settings()

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
