"""make pending balance field nullable

Revision ID: a3512390412c
Revises: 4606f30ddbdd
Create Date: 2024-11-26 21:56:58.732129

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3512390412c'
down_revision: Union[str, None] = '4606f30ddbdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pendingBalance', sa.Numeric(scale=9), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.drop_column('pendingBalance')

    # ### end Alembic commands ###
