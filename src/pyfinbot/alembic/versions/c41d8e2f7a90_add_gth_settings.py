"""add gth_settings (greentechhub-core settings store)

Revision ID: c41d8e2f7a90
Revises: a7ab2f6a51dc
Create Date: 2026-10-02 18:00:00.000000

Matches greentechhub_core.sqlalchemy.settings_table: one row per stored
value, keyed by scope ("app"/"user"), subject ("" for app rows) and key.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c41d8e2f7a90'
down_revision: Union[str, None] = 'a7ab2f6a51dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gth_settings',
    sa.Column('scope', sa.String(length=16), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('scope', 'subject', 'key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('gth_settings')
