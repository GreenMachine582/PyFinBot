"""PyFinBot's roles and permissions (greentechhub-core's Permission/Role),
resolved by greentechhub-fastapi's register_permissions from ROLE_BOOTSTRAP /
ROLE_GROUPS and the role grants managed at /admin/roles."""

from greentechhub_core.permissions import Permission, Role

USERS_MANAGE = Permission("users.manage")
"""Create and list users (the users API) and assign roles (/admin/roles)."""

SETTINGS_MANAGE = Permission("settings.manage")
"""Change app-wide settings (Settings › App), e.g. the site banner."""

ADMIN = Role(name="admin", permissions={USERS_MANAGE, SETTINGS_MANAGE})

ROLES = (ADMIN,)
