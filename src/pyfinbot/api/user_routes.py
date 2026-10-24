"""User accounts over the API (core/users.py's USER_STORE). Paths take the
account id (GET /api/auth/me gives your own). Creating and listing need
users.manage — there's no open registration; the rest is self-only.
DELETE deactivates rather than removing the account, so its transactions
stay; its sessions and tokens stop working at once."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from greentechhub_core.identity import Identity
from greentechhub_core.types import BadRequestError, ForbiddenError, NotFoundError
from greentechhub_core.users import UserAccount, UserExists, set_password
from greentechhub_fastapi.dependencies import get_current_identity
from greentechhub_fastapi.permissions import require_permission

from ..core.permissions import USERS_MANAGE
from ..core.users import USER_STORE, create_account
from ..schemas.user_schemas import UserBase, UserCreate, UserUpdate, user_out

router = APIRouter(prefix="/users", tags=["Users"])


def _exists(clash: UserExists) -> BadRequestError:
    return BadRequestError(f"A user with that {clash.field} already exists", code="user_exists",
                           details={"field": clash.field})


async def _own(identity: Identity, user_id: str, verb: str) -> UserAccount:
    if identity.subject != user_id:
        raise ForbiddenError(f"Not allowed to {verb} this user")
    account = await USER_STORE.get(user_id)
    if account is None:
        raise NotFoundError("User not found")
    return account


@router.post("/", response_model=UserBase, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    admin: Identity = Depends(require_permission(USERS_MANAGE)),
):
    """Create a user (users.manage only: there's no open registration — the
    first user comes from scripts/create_user.py plus ROLE_BOOTSTRAP)."""
    try:
        account = await create_account(user_in.username, user_in.password, email=user_in.email,
                                       display_name=user_in.display_name)
    except UserExists as clash:
        raise _exists(clash)
    except ValueError as exc:
        raise BadRequestError(str(exc), code="invalid_user")
    return user_out(account)


@router.get("/", response_model=list[UserBase])
async def list_users(admin: Identity = Depends(require_permission(USERS_MANAGE))):
    """Every user (users.manage only), by username."""
    return [user_out(account) for account in await USER_STORE.list_users()]


@router.get("/{user_id}", response_model=UserBase)
async def get_user(user_id: str, identity: Identity = Depends(get_current_identity)):
    return user_out(await _own(identity, user_id, "access"))


@router.put("/{user_id}", response_model=UserBase)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    identity: Identity = Depends(get_current_identity),
):
    account = await _own(identity, user_id, "modify")
    changes = user_update.model_dump(exclude_unset=True)
    password = changes.pop("password", None)
    try:
        if changes:
            account = await USER_STORE.update(account.id, changes) or account
        if password is not None:
            account = await set_password(USER_STORE, account.id, password) or account
    except UserExists as clash:
        raise _exists(clash)
    except ValueError as exc:
        raise BadRequestError(str(exc), code="invalid_user")
    return user_out(account)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, identity: Identity = Depends(get_current_identity)):
    """Deactivate your own account (its rows stay; it can't sign in again
    until an admin reactivates it)."""
    account = await _own(identity, user_id, "delete")
    await USER_STORE.update(account.id, {"active": False})
