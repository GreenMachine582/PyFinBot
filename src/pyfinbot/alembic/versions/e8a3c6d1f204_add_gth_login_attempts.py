"""add gth_login_attempts (greentechhub-core login throttle)

Revision ID: e8a3c6d1f204
Revises: d52e9f3a8b17
Create Date: 2026-10-06 10:00:00.000000

Matches greentechhub_core.sqlalchemy.login_attempts_table: one row per
throttled key ("account:<user id>" or "client:<ip>").
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8a3c6d1f204'
down_revision: Union[str, None] = 'd52e9f3a8b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gth_login_attempts',
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('failures', sa.Integer(), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('gth_login_attempts')
