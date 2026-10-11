"""add gth_audit_log (greentechhub-core audit log)

Revision ID: 7c02b9a0cfe8
Revises: e8a3c6d1f204
Create Date: 2026-10-11 18:46:32.271633

Matches greentechhub_core.sqlalchemy.audit_log_table: one row per audit entry,
read newest first at /admin/audit.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c02b9a0cfe8'
down_revision: Union[str, None] = 'e8a3c6d1f204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gth_audit_log',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor', sa.String(length=255), nullable=True),
    sa.Column('action', sa.String(length=128), nullable=False),
    sa.Column('target_type', sa.String(length=64), nullable=True),
    sa.Column('target_id', sa.String(length=255), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_gth_audit_log_actor', 'gth_audit_log', ['actor'], unique=False)
    op.create_index('ix_gth_audit_log_at', 'gth_audit_log', ['at'], unique=False)
    op.create_index('ix_gth_audit_log_target', 'gth_audit_log', ['target_type', 'target_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_gth_audit_log_target', table_name='gth_audit_log')
    op.drop_index('ix_gth_audit_log_at', table_name='gth_audit_log')
    op.drop_index('ix_gth_audit_log_actor', table_name='gth_audit_log')
    op.drop_table('gth_audit_log')
