"""add gth_notifications (greentechhub-core in-app notifications)

Revision ID: a9c4e7b2d5f1
Revises: f3b8d2c6a1e9
Create Date: 2026-10-16 12:00:00.000000

Matches greentechhub_core.sqlalchemy.notifications_table: one row per in-app
notice (each sync and import leaves one for the user who ran it), read at
/notifications and through the navbar bell.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c4e7b2d5f1'
down_revision: Union[str, None] = 'f3b8d2c6a1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gth_notifications',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('recipient', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('icon', sa.String(length=64), nullable=True),
    sa.Column('action_label', sa.String(length=255), nullable=True),
    sa.Column('action_url', sa.String(length=2048), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_gth_notifications_recipient_read_at', 'gth_notifications',
                    ['recipient', 'read_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_gth_notifications_recipient_read_at', table_name='gth_notifications')
    op.drop_table('gth_notifications')
