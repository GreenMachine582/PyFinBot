"""User accounts: greentechhub-core's users module over the gth_users and
gth_user_identities tables. USER_STORE is the one store every account
lookup goes through: the web sign-in and Settings (fastapi's store-backed
views), the API's token login and user routes, scripts/create_user.py and
the demo seed.

An account's id (32 hex characters) is what Transaction.user_id, settings,
role grants, the audit actor, notifications and API tokens all key on;
its username is only the login name. register_users (pyfinbot.py) makes
register_auth resolve every caller to their account, so a forward-auth
sign-in from Authentik is provisioned and linked on first use, and an
account set inactive is signed out on its next request."""

from greentechhub_core.sqlalchemy import SQLAlchemyUserStore
from greentechhub_core.users import UserAccount, set_password

from ..db.session import session_factory
from ..models.settings_models import USER_IDENTITIES_TABLE, USERS_TABLE

USER_STORE = SQLAlchemyUserStore(USERS_TABLE, USER_IDENTITIES_TABLE,
                                 async_session_factory=session_factory)


async def create_account(username: str, password: str, *, email: str | None = None,
                         display_name: str | None = None) -> UserAccount:
    """A new active account that signs in with `password`. Raises core's
    UserExists for a taken username or email, ValueError for a blank
    password or a username/email core refuses."""
    if not password:
        raise ValueError("a password is required")
    account = await USER_STORE.create(username, email=email, display_name=display_name)
    updated = await set_password(USER_STORE, account.id, password)
    assert updated is not None  # just created
    return updated
