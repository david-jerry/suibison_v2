"""add default value to pending balance field

Revision ID: ff8c709b8597
Revises: 23d455d93093
Create Date: 2024-11-27 06:57:50.193726

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff8c709b8597'
down_revision: Union[str, None] = '23d455d93093'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.alter_column('pendingBalance',
               existing_type=sa.NUMERIC(),
               nullable=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.alter_column('pendingBalance',
               existing_type=sa.NUMERIC(),
               nullable=True)

    # ### end Alembic commands ###
