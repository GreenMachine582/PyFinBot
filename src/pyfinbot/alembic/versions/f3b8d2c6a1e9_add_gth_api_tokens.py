"""add gth_api_tokens (greentechhub-core personal API tokens)

Revision ID: f3b8d2c6a1e9
Revises: 7c02b9a0cfe8
Create Date: 2026-10-16 09:30:00.000000

Matches greentechhub_core.sqlalchemy.api_tokens_table: one row per personal
API token, stored only as its SHA-256 (token_hash), created and revoked at
/settings › API tokens.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b8d2c6a1e9'
down_revision: Union[str, None] = '7c02b9a0cfe8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gth_api_tokens',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('owner', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('scopes', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_gth_api_tokens_owner', 'gth_api_tokens', ['owner'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_gth_api_tokens_owner', table_name='gth_api_tokens')
    op.drop_table('gth_api_tokens')
