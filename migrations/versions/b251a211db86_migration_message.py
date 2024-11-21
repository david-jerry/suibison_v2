"""Migration Message

Revision ID: b251a211db86
Revises: 098f9ca70af8
Create Date: 2024-11-21 19:03:04.466989

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b251a211db86'
down_revision: Union[str, None] = '098f9ca70af8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('peending_transactions',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Numeric(scale=9), nullable=False),
    sa.Column('userUid', sa.Uuid(), nullable=True),
    sa.Column('commpleted', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['userUid'], ['users.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('peending_transactions')
    # ### end Alembic commands ###