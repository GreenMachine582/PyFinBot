"""v0.1 - transactions

Revision ID: 8101046ced8e
Revises: d424b7108349
Create Date: 2025-05-07 17:49:19.721983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8101046ced8e'
down_revision: Union[str, None] = 'd424b7108349'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('transaction', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('transaction', 'stock_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint('transaction_user_id_fkey', 'transaction', type_='foreignkey')
    op.create_foreign_key(None, 'transaction', 'user', ['user_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'transaction', type_='foreignkey')
    op.create_foreign_key('transaction_user_id_fkey', 'transaction', 'user', ['user_id'], ['id'])
    op.alter_column('transaction', 'stock_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('transaction', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###
