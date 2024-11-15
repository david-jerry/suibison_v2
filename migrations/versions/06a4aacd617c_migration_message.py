"""Migration Message

Revision ID: 06a4aacd617c
Revises: bf6095a3dc92
Create Date: 2024-11-15 19:07:20.279666

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06a4aacd617c'
down_revision: Union[str, None] = 'bf6095a3dc92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'activities', ['uid'])
    op.create_unique_constraint(None, 'celery_beat', ['uid'])
    op.create_unique_constraint(None, 'matrix_pool', ['uid'])
    op.create_unique_constraint(None, 'matrix_users', ['uid'])
    op.create_unique_constraint(None, 'referrals', ['uid'])
    op.create_unique_constraint(None, 'token_meter', ['uid'])
    op.create_unique_constraint(None, 'user_stakings', ['uid'])
    op.create_unique_constraint(None, 'users', ['uid'])
    op.create_unique_constraint(None, 'wallets', ['uid'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'wallets', type_='unique')
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_constraint(None, 'user_stakings', type_='unique')
    op.drop_constraint(None, 'token_meter', type_='unique')
    op.drop_constraint(None, 'referrals', type_='unique')
    op.drop_constraint(None, 'matrix_users', type_='unique')
    op.drop_constraint(None, 'matrix_pool', type_='unique')
    op.drop_constraint(None, 'celery_beat', type_='unique')
    op.drop_constraint(None, 'activities', type_='unique')
    # ### end Alembic commands ###
