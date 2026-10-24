"""baseline schema

Revision ID: 6f5da3f3fd6c
Revises:
Create Date: 2026-10-21 08:37:45.292933

The whole schema in one revision, replacing the history before it (there
was no production database to carry forward): PyFinBot's stock, dividend
and transaction tables, and greentechhub-core's gth_* tables, including the
user accounts (gth_users) and their linked sign-ins (gth_user_identities)
that transaction.user_id references.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '6f5da3f3fd6c'
down_revision: Union[str, None] = None
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
    op.create_table('gth_login_attempts',
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('failures', sa.Integer(), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )
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
    op.create_index('ix_gth_notifications_recipient_read_at', 'gth_notifications', ['recipient', 'read_at'], unique=False)
    op.create_table('gth_one_time_tokens',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('purpose', sa.String(length=64), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index('ix_gth_one_time_tokens_subject_purpose', 'gth_one_time_tokens', ['subject', 'purpose'], unique=False)
    op.create_table('gth_role_grants',
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=255), nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('subject', 'role')
    )
    op.create_table('gth_settings',
    sa.Column('scope', sa.String(length=16), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('scope', 'subject', 'key')
    )
    op.create_table('gth_users',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('username', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('email_verified', sa.Boolean(), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('auth_source', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('stock',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
    sa.Column('market', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('create_datetime', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.Column('write_datetime', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'market', name='unique_symbol_market')
    )
    op.create_index(op.f('ix_stock_market'), 'stock', ['market'], unique=False)
    op.create_index(op.f('ix_stock_name'), 'stock', ['name'], unique=False)
    op.create_index(op.f('ix_stock_symbol'), 'stock', ['symbol'], unique=False)
    op.create_table('dividend',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('stock_id', sa.Integer(), nullable=False),
    sa.Column('ex_date', sa.Date(), nullable=False),
    sa.Column('pay_date', sa.Date(), nullable=True),
    sa.Column('amount_per_share', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('create_datetime', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.Column('write_datetime', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['stock_id'], ['stock.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stock_id', 'ex_date', name='unique_stock_ex_date')
    )
    op.create_index(op.f('ix_dividend_ex_date'), 'dividend', ['ex_date'], unique=False)
    op.create_index(op.f('ix_dividend_stock_id'), 'dividend', ['stock_id'], unique=False)
    op.create_table('gth_user_identities',
    sa.Column('provider', sa.String(length=64), nullable=False),
    sa.Column('external_subject', sa.String(length=255), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['gth_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('provider', 'external_subject')
    )
    op.create_index('ix_gth_user_identities_user_id', 'gth_user_identities', ['user_id'], unique=False)
    op.create_table('transaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('stock_id', sa.Integer(), nullable=False),
    sa.Column('transaction_date', sa.Date(), nullable=False),
    sa.Column('type', sa.Enum('BUY', 'SELL', name='typeenum'), nullable=False),
    sa.Column('units', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('price', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('total_value', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('fees', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('cost', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('fy', sa.Integer(), nullable=False),
    sa.Column('create_datetime', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.Column('write_datetime', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['stock_id'], ['stock.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['gth_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_user_id'), 'transaction', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_transaction_user_id'), table_name='transaction')
    op.drop_table('transaction')
    op.drop_index('ix_gth_user_identities_user_id', table_name='gth_user_identities')
    op.drop_table('gth_user_identities')
    op.drop_index(op.f('ix_dividend_stock_id'), table_name='dividend')
    op.drop_index(op.f('ix_dividend_ex_date'), table_name='dividend')
    op.drop_table('dividend')
    op.drop_index(op.f('ix_stock_symbol'), table_name='stock')
    op.drop_index(op.f('ix_stock_name'), table_name='stock')
    op.drop_index(op.f('ix_stock_market'), table_name='stock')
    op.drop_table('stock')
    op.drop_table('gth_users')
    op.drop_table('gth_settings')
    op.drop_table('gth_role_grants')
    op.drop_index('ix_gth_one_time_tokens_subject_purpose', table_name='gth_one_time_tokens')
    op.drop_table('gth_one_time_tokens')
    op.drop_index('ix_gth_notifications_recipient_read_at', table_name='gth_notifications')
    op.drop_table('gth_notifications')
    op.drop_table('gth_login_attempts')
    op.drop_index('ix_gth_audit_log_target', table_name='gth_audit_log')
    op.drop_index('ix_gth_audit_log_at', table_name='gth_audit_log')
    op.drop_index('ix_gth_audit_log_actor', table_name='gth_audit_log')
    op.drop_table('gth_audit_log')
    op.drop_index('ix_gth_api_tokens_owner', table_name='gth_api_tokens')
    op.drop_table('gth_api_tokens')
