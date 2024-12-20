"""Migration Message

Revision ID: 5f8fb9bce003
Revises: 46f74f0b2253
Create Date: 2024-11-16 21:53:59.741151

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f8fb9bce003'
down_revision: Union[str, None] = '46f74f0b2253'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('referrals', sa.Column('userId', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.drop_constraint('referrals_referrerUid_fkey', 'referrals', type_='foreignkey')
    op.drop_column('referrals', 'referrerUid')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('referrals', sa.Column('referrerUid', sa.UUID(), autoincrement=False, nullable=True))
    op.create_foreign_key('referrals_referrerUid_fkey', 'referrals', 'users', ['referrerUid'], ['uid'])
    op.drop_column('referrals', 'userId')
    # ### end Alembic commands ###
