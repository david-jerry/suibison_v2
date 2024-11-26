"""make referrer_id field nullable

Revision ID: 4606f30ddbdd
Revises: 2e4d8c80402e
Create Date: 2024-11-25 20:30:52.634773

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4606f30ddbdd'
down_revision: Union[str, None] = '2e4d8c80402e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('celery_beat', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('matrix_pool', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('matrix_users', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('peending_transactions', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('referrals', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('token_meter', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('user_stakings', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('referrer_id',
               existing_type=sa.UUID(),
               nullable=True)
        batch_op.create_unique_constraint(None, ['uid'])

    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['uid'])

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')
        batch_op.alter_column('referrer_id',
               existing_type=sa.UUID(),
               nullable=False)

    with op.batch_alter_table('user_stakings', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('token_meter', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('referrals', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('peending_transactions', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('matrix_users', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('matrix_pool', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('celery_beat', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    # ### end Alembic commands ###
