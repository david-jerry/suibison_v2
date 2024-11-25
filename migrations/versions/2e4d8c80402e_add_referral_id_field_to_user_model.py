"""add referral id field to user model

Revision ID: 2e4d8c80402e
Revises: aabf1acbd851
Create Date: 2024-11-25 20:16:50.568563

"""
from typing import Sequence, Union
import sqlmodel

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2e4d8c80402e'
down_revision: Union[str, None] = 'aabf1acbd851'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('celery_beat',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('task_name', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
    sa.Column('task_args', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('task_kwargs', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('crontab', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('schedule_type', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(), nullable=False),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    op.create_table('matrix_pool',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('raisedPoolAmount', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalReferrals', sa.Integer(), nullable=False),
    sa.Column('startDate', postgresql.TIMESTAMP(), nullable=True),
    sa.Column('endDate', postgresql.TIMESTAMP(), nullable=True),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    op.create_table('token_meter',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('tokenAddress', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('tokenPhrase', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('tokenPrivateKey', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('totalAmountCollected', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalCap', sa.Numeric(scale=9), nullable=False),
    sa.Column('tokenPrice', sa.Numeric(scale=9), nullable=False),
    sa.Column('suiUsdPrice', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalDeposited', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalWithdrawn', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalSentToGMP', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalDistributedByGMP', sa.Numeric(scale=9), nullable=False),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    with op.batch_alter_table('token_meter', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_token_meter_tokenAddress'), ['tokenAddress'], unique=True)
        batch_op.create_index(batch_op.f('ix_token_meter_tokenPhrase'), ['tokenPhrase'], unique=True)
        batch_op.create_index(batch_op.f('ix_token_meter_tokenPrivateKey'), ['tokenPrivateKey'], unique=True)

    op.create_table('users',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('userId', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
    sa.Column('firstName', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('lastName', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('phoneNumber', sqlmodel.sql.sqltypes.AutoString(length=14), nullable=True),
    sa.Column('dob', sa.DATE(), nullable=True),
    sa.Column('image', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('passwordHash', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('isBlocked', sa.Boolean(), nullable=False),
    sa.Column('usedSpeedBoost', sa.Boolean(), nullable=True),
    sa.Column('isAdmin', sa.Boolean(), nullable=False),
    sa.Column('isSuperuser', sa.Boolean(), nullable=False),
    sa.Column('hasMadeFirstDeposit', sa.Boolean(), nullable=False),
    sa.Column('rank', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=True),
    sa.Column('totalTeamVolume', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalReferrals', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalReferralsStakes', sa.Numeric(scale=9), nullable=True),
    sa.Column('totalNetwork', sa.BIGINT(), nullable=False),
    sa.Column('referrer_id', sa.Uuid(), nullable=False),
    sa.Column('joined', sa.DateTime(), nullable=False),
    sa.Column('lastRankEarningAddedAt', sa.DateTime(), nullable=False),
    sa.Column('updatedAt', postgresql.TIMESTAMP(), nullable=False),
    sa.ForeignKeyConstraint(['referrer_id'], ['users.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_userId'), ['userId'], unique=False)

    op.create_table('activities',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('activityType', sa.Enum('DEPOSIT', 'WITHDRAWAL', 'RANKING', 'REFERRAL', 'FASTBONUS', 'MATRIXPOOL', 'MATRIXPOOLTOPUP', 'TOKENPURCHASE', 'WELCOME', 'REFERRALBONUS', name='activitytype'), nullable=False),
    sa.Column('strDetail', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('amountDetail', sa.Numeric(scale=9), nullable=True),
    sa.Column('suiAmount', sa.Numeric(scale=9), nullable=True),
    sa.Column('userUid', sa.Uuid(), nullable=False),
    sa.Column('created', postgresql.TIMESTAMP(), nullable=True),
    sa.ForeignKeyConstraint(['userUid'], ['users.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    op.create_table('matrix_users',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('matrixPoolUid', sa.Uuid(), nullable=True),
    sa.Column('userId', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('referralsAdded', sa.Integer(), nullable=False),
    sa.Column('matrixEarninig', sa.Numeric(scale=9), nullable=False),
    sa.Column('matrixShare', sa.Numeric(scale=2), nullable=False),
    sa.ForeignKeyConstraint(['matrixPoolUid'], ['matrix_pool.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    op.create_table('peending_transactions',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Numeric(scale=9), nullable=False),
    sa.Column('userUid', sa.Uuid(), nullable=True),
    sa.Column('commpleted', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['userUid'], ['users.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    op.create_table('referrals',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('level', sa.Integer(), nullable=True),
    sa.Column('theirUserId', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('userId', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('reward', sa.Numeric(scale=9), nullable=True),
    sa.Column('stake', sa.Numeric(scale=9), nullable=True),
    sa.Column('userUid', sa.Uuid(), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['userUid'], ['users.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    op.create_table('user_stakings',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('roi', sa.Numeric(scale=2), nullable=False),
    sa.Column('deposit', sa.Numeric(scale=9), nullable=False),
    sa.Column('userUid', sa.Uuid(), nullable=True),
    sa.Column('start', postgresql.TIMESTAMP(), nullable=True),
    sa.Column('end', postgresql.TIMESTAMP(), nullable=True),
    sa.Column('nextRoiIncrease', postgresql.TIMESTAMP(), nullable=True),
    sa.ForeignKeyConstraint(['userUid'], ['users.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('uid')
    )
    op.create_table('wallets',
    sa.Column('uid', sa.UUID(), nullable=False),
    sa.Column('address', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('phrase', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('privateKey', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('balance', sa.Numeric(scale=9), nullable=False),
    sa.Column('earnings', sa.Numeric(scale=9), nullable=False),
    sa.Column('availableReferralEarning', sa.Numeric(scale=9), nullable=False),
    sa.Column('expectedRankBonus', sa.Numeric(scale=9), nullable=False),
    sa.Column('weeklyRankEarnings', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalDeposit', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalTokenPurchased', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalRankBonus', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalFastBonus', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalWithdrawn', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalReferralBonus', sa.Numeric(scale=9), nullable=False),
    sa.Column('totalReferralEarnings', sa.Numeric(scale=9), nullable=True),
    sa.Column('userUid', sa.Uuid(), nullable=True),
    sa.Column('createdAt', postgresql.TIMESTAMP(), nullable=True),
    sa.ForeignKeyConstraint(['userUid'], ['users.uid'], ),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('phrase'),
    sa.UniqueConstraint('privateKey'),
    sa.UniqueConstraint('uid')
    )
    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_wallets_address'), ['address'], unique=True)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('wallets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_wallets_address'))

    op.drop_table('wallets')
    op.drop_table('user_stakings')
    op.drop_table('referrals')
    op.drop_table('peending_transactions')
    op.drop_table('matrix_users')
    op.drop_table('activities')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_userId'))

    op.drop_table('users')
    with op.batch_alter_table('token_meter', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_token_meter_tokenPrivateKey'))
        batch_op.drop_index(batch_op.f('ix_token_meter_tokenPhrase'))
        batch_op.drop_index(batch_op.f('ix_token_meter_tokenAddress'))

    op.drop_table('token_meter')
    op.drop_table('matrix_pool')
    op.drop_table('celery_beat')
    # ### end Alembic commands ###
