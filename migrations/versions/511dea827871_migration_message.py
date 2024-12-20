"""Migration Message

Revision ID: 511dea827871
Revises: c3298366e994
Create Date: 2024-11-18 20:40:53.826524

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '511dea827871'
down_revision: Union[str, None] = 'c3298366e994'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'firstName',
               existing_type=sa.VARCHAR(length=12),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               existing_nullable=True)
    op.alter_column('users', 'lastName',
               existing_type=sa.VARCHAR(length=12),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               existing_nullable=True)
    op.alter_column('users', 'phoneNumber',
               existing_type=sa.VARCHAR(length=12),
               type_=sqlmodel.sql.sqltypes.AutoString(length=14),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'phoneNumber',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=14),
               type_=sa.VARCHAR(length=12),
               existing_nullable=True)
    op.alter_column('users', 'lastName',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=sa.VARCHAR(length=12),
               existing_nullable=True)
    op.alter_column('users', 'firstName',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=sa.VARCHAR(length=12),
               existing_nullable=True)
    # ### end Alembic commands ###
