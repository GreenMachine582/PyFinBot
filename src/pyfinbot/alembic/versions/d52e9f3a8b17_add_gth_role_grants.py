"""add gth_role_grants (greentechhub-core role grants)

Revision ID: d52e9f3a8b17
Revises: c41d8e2f7a90
Create Date: 2026-10-03 10:00:00.000000

Matches greentechhub_core.sqlalchemy.role_grants_table: one row per role
assigned to a subject at /admin/roles.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd52e9f3a8b17'
down_revision: Union[str, None] = 'c41d8e2f7a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gth_role_grants',
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=255), nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('subject', 'role')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('gth_role_grants')
