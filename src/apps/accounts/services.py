from decimal import Decimal
import pprint
import random
import uuid

from datetime import date, datetime, timedelta
from typing import Annotated, Any, List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from apscheduler.schedulers.background import BackgroundScheduler  # runs tasks in the background
from apscheduler.triggers.cron import CronTrigger  # allows us to specify a recurring time for execution

from sqlalchemy import Date, cast
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from src.apps.accounts.dependencies import user_exists_check
from src.apps.accounts.enum import ActivityType
from src.apps.accounts.models import Activities, MatrixPool, MatrixPoolUsers, TokenMeter, User, UserReferral, UserStaking, UserWallet
from src.apps.accounts.schemas import ActivitiesRead, AllStatisticsRead, MatrixUserCreateUpdate, TokenMeterCreate, TokenMeterUpdate, UserCreateOrLoginSchema, UserRead, UserUpdateSchema
from src.utils.calculations import get_rank
from src.utils.sui_json_rpc_apis import SUI
from src.errors import ActivePoolNotFound, InsufficientBalance, InvalidStakeAmount, InvalidTelegramAuthData, OnlyOneTokenMeterRequired, TokenMeterDoesNotExists, TokenMeterExists, UserAlreadyExists, UserBlocked, UserNotFound
from src.utils.hashing import createAccessToken, verifyTelegramAuthData
from src.utils.logger import LOGGER
from src.config.settings import Config
from src.db.redis import add_level_referral, get_level_referrers

from mnemonic import Mnemonic
from sui_python_sdk.wallet import SuiWallet

now = datetime.now()

class AdminServices:
    async def createTokenRecord(self, form_data: TokenMeterCreate, session: AsyncSession):
        db_result = await session.exec(select(TokenMeter).where(TokenMeter.tokenAddress == form_data.tokenAddress))
        existingTokenMeter = db_result.first()
        tm_result = await session.exec(select(TokenMeter))
        allTokenMeters = tm_result.all()
        
        if existingTokenMeter is not None:
            raise TokenMeterExists()
        
        if len(allTokenMeters) > 0:
            raise OnlyOneTokenMeterRequired()
        
        form_dict = form_data.model_dump()
        tokenMeter = TokenMeter(**form_dict)
        session.add(tokenMeter)
        await session.commit()
        return tokenMeter

    async def updateTokenRecord(self, form_data: TokenMeterUpdate, session: AsyncSession):
        db_result = await session.exec(select(TokenMeter).where(TokenMeter.tokenAddress == form_data.tokenAddress))
        existingTokenMeter = db_result.first()
        
        if existingTokenMeter is None:
            raise TokenMeterDoesNotExists()
                
        form_dict = form_data.model_dump()
        
        for k, v in form_dict.items():
            if v is not None:
                setattr(existingTokenMeter, k, v)
        
        session.add(existingTokenMeter)
        await session.commit()
        await session.refresh(existingTokenMeter)
        return existingTokenMeter
    
    async def addNewPoolUser(self, poolUser: MatrixUserCreateUpdate, session: AsyncSession):
        db_pool_result = await session.exec(select(MatrixPool).where(MatrixPool.endDate <= now))
        active_pool = db_pool_result.first()
        if active_pool is None:
            raise ActivePoolNotFound()
        
        db_pool_user = await session.exec(select(MatrixPoolUsers).where(MatrixPool.uid == active_pool.uid))
        pool_user = db_pool_user.first()
        if pool_user is None:
            new_user = MatrixPoolUsers(
                userId = poolUser.userId,
                referralsAdded = poolUser.referralsAdded
            )
            session.add(new_user)
            await session.commit()
            return new_user
        pool_user.userId = poolUser.userId
        pool_user.referralsAdded = poolUser.referralsAdded
        await session.commit()
        await session.refresh(pool_user)
        return pool_user
        
    async def statRecord(self, session: AsyncSession) -> AllStatisticsRead:
        # Step 1: Group referred users by date, counting referrals per day
        daily_referrals_query = (
            select(
                cast(User.joined, Date).label("join_date"),
                func.count(User.userId).label("daily_referrals")
            )
            .where(User.referredByUserId != None)
            .group_by(cast(User.joined, Date))
        )

        # Execute the query to get daily referral counts
        daily_referrals = await session.exec(daily_referrals_query)
        daily_referrals = daily_referrals.all()

        # Step 2: Calculate the total referrals and the average referrals per day
        total_days_with_referrals = len(daily_referrals)
        total_referred_users = sum(row.daily_referrals for row in daily_referrals)
        average_daily_referrals = int(total_referred_users / total_days_with_referrals) if total_days_with_referrals else 0


        # Query the total amount staked by summing deposits from the userStaking model
        total_staked_query = select(func.sum(UserWallet.totalDeposit))
        total_staked_result = await session.exec(total_staked_query)
        total_staked = total_staked_result.scalar() or Decimal(0.00)
        
        # Query to get the total amount raised in the metrix pool
        total_pool_query = select(func.sum(MatrixPool.raisedPoolAmount))
        total_pool_result = await session.exec(total_pool_query)
        total_pool_generated = total_pool_result.scalar() or Decimal(0.00)
        
        return AllStatisticsRead(
            averageDailyReferral=average_daily_referrals,
            totalAmountStaked=total_staked,
            totalMatrixPoolGenerated=total_pool_generated,
        )

    async def getAllTransactions(self, date: date, session: AsyncSession):
        if date is not None:
            transactions = await session(select(Activities).where(Activities.activityType == ActivityType.DEPOSIT, Activities.activityType == ActivityType.WITHDRAWAL).where(Activities.created.date() >= date).order_by(Activities.created))
            return transactions.all()
        transactions = await session(select(Activities).where(Activities.activityType == ActivityType.DEPOSIT, Activities.activityType == ActivityType.WITHDRAWAL).order_by(Activities.created))
        return transactions.all()

    async def getAllActivities(self, date: date, session: AsyncSession):
        if date is not None:
            allActivities = await session(select(Activities).where(Activities.created.date() >= date).order_by(Activities.created))
            return allActivities.all()
        allActivities = await session(select(Activities).order_by(Activities.created))
        return allActivities.all()
    
    async def getAllUsers(self, date: date, session: AsyncSession):
        if date is not None:
            users: Page[User] = await paginate(session, select(User).where(User.isSuperuser == False).where(User.joined.date() >= date).order_by(User.joined, User.firstName))
            return users
        users = await paginate(session, select(User).order_by(User.isSuperuser == False).order_by(User.joined, User.firstName))
        return users
    
    async def banUser(self, userId: str, session: AsyncSession) -> bool:
        db_result = await session.exec(select(User).where(User.userId == userId))
        user = db_result.first()
        if user is None:
            raise UserNotFound()
        
        user.isBlocked = False if user.isBlocked else True
        await session.commit()
        await session.refresh(user)
        return True
    
    
class UserServices:
    async def create_referral_level(self, user: User, referral_userId: str, referral_name: str, level: int, session: AsyncSession):
        if level < 6:
            user.totalNetwork += 1
            user.totalReferrals += 1 if level == 1 else 0
            await add_level_referral(user.userId, level=level, referralId=referral_userId, balance=Decimal(0.00), name=referral_name)
            
            session.add(Activities(activityType=ActivityType.REFERRAL, strDetail=f"", userUid=user.uid))
            await session.commit()            
            await self.create_referral_level(user.referrer, referral_userId, referral_name, level + 1, session)
        return None
    
    async def create_referrer(self, referrer: Optional[str], new_user: User, session: AsyncSession):
        if referrer is not None:                
            db_result = await session.exec(select(User).where(User.userId == referrer))
            referring_user = db_result.first()
            
            # Save the referral level down to the 5th level in redis for improved performance
            if referring_user is not None:
                fast_boost_time = referring_user.joined + timedelta(hours=24)
                db_referrals = await session.exec(select(UserReferral).where(UserReferral.userUid == referring_user.uid))
                referrals = db_referrals.all()
                
                # check for fast boost and credit the users wallet balance accordingly
                if referring_user.joined < fast_boost_time and len(referrals) >= 2:
                    referring_user.wallet.totalFastBonus += Decimal(3.00)
                    referring_user.wallet.balance += Decimal(3.00)
                    
                new_referral = UserReferral(
                    userUid=referring_user.uid,
                )
                session.add(new_referral)
                LOGGER.debug(f"NEW REFERRAL:: {new_referral.userUid}")
                
                referral_name = f"{new_user.firstName} {new_user.lastName}" if new_user.firstName is not None and new_user.lastName else None
                self.create_referral_level(referring_user, new_user.userId, referral_name, 1, session)
        return None
                
    async def create_wallet(self, user: User, session: AsyncSession):
        mnemonic_phrase = Mnemonic("english").generate(strength=256)
        # Generate a new wallet which includes the wallet address and mnemonic phrase
        my_wallet = SuiWallet(mnemonic=mnemonic_phrase)
        my_address = my_wallet.get_address()
        my_private_key = my_wallet.private_key.hex()
        
        # Save the new wallet in the database
        new_wallet = UserWallet(address=my_address, phrase=mnemonic_phrase, privateKey=my_private_key, userUid=user.uid)
        session.add(new_wallet)
        return new_wallet
        
    async def create_staking_account(self, user: User, session: AsyncSession):
        # Create a new staking account for the user wallet to store their staking details
        new_staking = UserStaking(userUid=user.uid)
        LOGGER.debug(f"NEW_STAKING:: {new_staking}")
        session.add(new_staking)
        return new_staking

    async def calculate_rank_earning(self, user: User, session: AsyncSession):
        db_result = await session.exec(select(UserReferral).where(UserReferral.userUid == user.uid))
        referrals = db_result.all()
        rankErning, rank = await get_rank(user.totalTeamVolume, user.wallet.totalDeposit, referrals)
        
        if user.rank != rank:
            user.rank = rank
        
        user.wallet.weeklyRankEarnings = rankErning
        
        # Calculate days since last rank earning
        days_since_last_earning = (now.date() - user.lastRankEarningAddedAt.date()).days

        # Calculate weeks using integer division (discarding remainder)
        weeks_earned = days_since_last_earning // 7

        # Check if there are weeks to be added
        if weeks_earned > 0:
            user.wallet.earnings += user.wallet.weeklyRankEarnings * weeks_earned
            user.wallet.totalRankBonus += user.wallet.weeklyRankEarnings * weeks_earned
            user.wallet.expectedRankBonus += user.wallet.weeklyRankEarnings * weeks_earned

            # Update lastRankEarningAddedAt to reflect the latest calculation
            user.lastRankEarningAddedAt = now - timedelta(days=days_since_last_earning % 7)

        session.add(user)
        return None

    async def register_new_user(self, admin: bool, referrer: Optional[str], form_data: UserCreateOrLoginSchema, session: AsyncSession) -> User:
        # validate the telegram string
        if not verifyTelegramAuthData(form_data.telegram_init_data):
            raise InvalidTelegramAuthData()
                
        user = await user_exists_check(form_data.userId, session)
                
        if user is None:
            new_user = User(
                userId=form_data.userId,
                firstName=form_data.firstName,
                lastName=form_data.lastName,
                phoneNumber=form_data.phoneNumber,
                isAdmin=admin,
            )
            session.add(new_user)
            stake = await self.create_staking_account(new_user, session)
            LOGGER.debug(f"Stake:: {stake}")
            # Create an activity record for this new user
            new_activity = Activities(activityType=ActivityType.WELCOME, strDetail="Welcome to SUI-Bison", userUid=new_user.uid)
            session.add(new_activity)
            
            new_wallet = await self.create_wallet(new_user, session)
            LOGGER.debug(f"NEW WALLET:: {new_wallet}")
            
            await session.commit()
            await session.refresh(new_user)
            

            if referrer is not None:
                await self.create_referrer(referrer, new_user, session)

            # generate access and refresh token so long the telegram init data is valid
            accessToken = createAccessToken(
                user_data={
                    "userId": new_user.userId,
                },
                expiry=timedelta(seconds=Config.ACCESS_TOKEN_EXPIRY)
            )
            refreshToken = createAccessToken(
                user_data={
                    "userId": new_user.userId,
                },
                refresh=True,
                expiry=timedelta(days=7)
            )
            return accessToken, refreshToken, new_user
    
        # check if the user is blocked
        if user is not None and user.isBlocked:
            raise UserBlocked()
        
        # update the users rank record immediately they open the webapp and the weeks match up
        if user is not None:
            await self.calculate_rank_earning(user, session)
        
        # # Process active stake balances and earnings
        # if user is not None and user.wallet.staking.endingAt <= datetime.now():
        #     active_stake = user.wallet.staking
        #     await self.calculate_and_update_staked_interest_every_5_days(session, active_stake)
        
        # generate access and refresh token so long the telegram init data is valid
        accessToken = createAccessToken(
            user_data={
                "userId": user.userId,
            },
            expiry=timedelta(seconds=Config.ACCESS_TOKEN_EXPIRY)
        )
        refreshToken = createAccessToken(
            user_data={
                "userId": user.userId,
            },
            refresh=True,
            expiry=timedelta(days=7)
        )
        
        return accessToken, refreshToken, user
    
    async def return_user_by_userId(self, userId: int, session: AsyncSession):
        db_result = await session.exec(select(User).where(User.userId == userId))
        user = db_result.first()
        if user is None:
            raise UserNotFound()
        return user
    
    async def updateUserProfile(self, user: User, form_data: UserUpdateSchema, session: AsyncSession):
        form_dict = form_data.model_dump()
        
        for k, v in form_dict.items():
            if v is not None:
                setattr(user, k, v)
                
        await session.commit()
        await session.refresh(user)
        return user

    async def getUserActivities(self, user: User, session: AsyncSession):
        query = select(Activities).where(Activities.userUid == user.uid).order_by(Activities.created).limit(25)
        db=await session.exec(query)
        allActivities = db.all()
        return allActivities
    
