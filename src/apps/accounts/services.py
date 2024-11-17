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
from src.apps.accounts.schemas import ActivitiesRead, AdminLogin, AllStatisticsRead, MatrixUserCreateUpdate, TokenMeterCreate, TokenMeterUpdate, UserCreateOrLoginSchema, UserRead, UserUpdateSchema
from src.utils.calculations import get_rank
from src.utils.sui_json_rpc_apis import SUI
from src.errors import ActivePoolNotFound, InsufficientBalance, InvalidCredentials, InvalidStakeAmount, InvalidTelegramAuthData, OnlyOneTokenMeterRequired, ReferrerNotFound, TokenMeterDoesNotExists, TokenMeterExists, UserAlreadyExists, UserBlocked, UserNotFound
from src.utils.hashing import createAccessToken, verifyHashKey, verifyTelegramAuthData
from src.utils.logger import LOGGER
from src.config.settings import Config
from src.db.redis import add_level_referral, get_level_referrers, get_sui_usd_price

from mnemonic import Mnemonic
from sui_python_sdk.wallet import SuiWallet

now = datetime.now()
scheduler = BackgroundScheduler({
    "apscheduler.jobstores.default": {
        "type": "sqlalchemy",
        "url": Config.DATABASE_URL
    },
    'apscheduler.executors.default': {
        'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
        'max_workers': '50'
    },
    'apscheduler.executors.processpool': {
        'type': 'processpool',
        'max_workers': '20'
    },
    'apscheduler.job_defaults.coalesce': 'false',
    'apscheduler.job_defaults.max_instances': '12',
    'apscheduler.timezone': 'UTC',
})


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
    async def create_referral_level(self, new_user: User, referring_user: User, level: int, session: AsyncSession):
        referrer = referring_user
        
        if level < 6:
            referrer.totalNetwork += 1
            referrer.totalReferrals += 1 if level == 1 else 0
            
            new_referral = UserReferral(
                level=level,
                theirUserId=new_user.userId,
                userUid=new_user.uid,
                userId=referrer.userId,
            )
            session.add(new_referral)
            session.add(Activities(activityType=ActivityType.REFERRAL, strDetail=f"New Level {level} referral added", userUid=referrer.uid))
            # await session.commit()            
            if referring_user.referrer is not None:
                db_result = await session.exec(select(User).where(User.userId == referring_user.referrer.userId))
                referrers_referrer = db_result.first()
                await self.create_referral_level(new_user, referrers_referrer, level + 1, session)
        return None
    
    async def create_referrer(self, referrer_userId: Optional[str], new_user: User, session: AsyncSession):
        if referrer_userId is not None:                
            db_result = await session.exec(select(User).where(User.userId == referrer_userId))
            referring_user = db_result.first()
            
            # Save the referral level down to the 5th level in redis for improved performance
            if referring_user is None:
                raise ReferrerNotFound()

            fast_boost_time = referring_user.joined + timedelta(hours=24)
            db_referrals = await session.exec(select(UserReferral).where(UserReferral.userId == referrer_userId).where(UserReferral.level == 1))
            referrals = db_referrals.all()
            
            # check for fast boost and credit the users wallet balance accordingly
            if referring_user.joined < fast_boost_time and len(referrals) >= 2:
                referring_user.wallet.totalFastBonus += Decimal(3.00)
                referring_user.wallet.balance += Decimal(3.00)
                                
            await self.create_referral_level(new_user, referring_user, 1, session)
        return None
                
    async def add_referrer_earning(self, referrer: Optional[str], amount: Decimal, level: int, session: AsyncSession):
        if referrer is not None:                
            db_result = await session.exec(select(User).where(User.userId == referrer))
            user = db_result.first()
            
            percentage = Decimal(0.1)
            if level == 2:
                percentage = Decimal(0.05)
            elif level == 3:
                percentage = Decimal(0.03)
            elif level == 4:
                percentage = Decimal(0.02)
            elif level == 5:
                percentage = Decimal(0.01)
                
            
            # Save the referral level down to the 5th level in redis for improved performance
            if user is not None:
                user.wallet.earnings += percentage * amount
                user.totalTeamVolume += amount
                ref_activity = Activities(activityType=ActivityType.REFERRAL, strDetail="Referral Bonus", suiAmount=Decimal(percentage * amount), userId=referrer)
                session.add(ref_activity)
                if level < 6:
                    return self.add_referrer_earning(user.referrer.userId, amount, level + 1, session)
        return None
                
    async def create_wallet(self, user: User, session: AsyncSession):
        mnemonic_phrase = Mnemonic("english").generate(strength=128)
        # Generate a new wallet which includes the wallet address and mnemonic phrase
        my_wallet = SuiWallet(mnemonic=mnemonic_phrase)
        my_address = my_wallet.get_address()
        my_private_key = my_wallet.private_key.hex()
        signer = my_wallet.full_private_key
        
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
        db_result = await session.exec(select(UserReferral).where(UserReferral.userUid == user.uid).where(UserReferral.level == 1))
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

    async def authenticate_user(self, form_data: AdminLogin, session):     
        user = await user_exists_check(form_data.userId, session)
        
        valid_password = verifyHashKey(form_data.password, user.passwordHash)
        if not valid_password:
            raise InvalidCredentials()
                
        # check if the user is blocked
        if user is not None and user.isBlocked:
            raise UserBlocked()
        
        # update the users rank record immediately they open the webapp and the weeks match up
        if user is not None:
            await self.calculate_rank_earning(user, session)
                
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

    async def register_new_user(self, admin: bool, referrer_userId: Optional[str], form_data: UserCreateOrLoginSchema, session: AsyncSession) -> User:
        # validate the telegram string
        if not verifyTelegramAuthData(form_data.telegram_init_data):
            raise InvalidTelegramAuthData()
                
        user = await user_exists_check(form_data.userId, session)
                
        if user is None:
            user = User(
                userId=form_data.userId,
                firstName=form_data.firstName,
                lastName=form_data.lastName,
                phoneNumber=form_data.phoneNumber,
                isAdmin=admin,
            )
            session.add(user)
            stake = await self.create_staking_account(user, session)
            LOGGER.debug(f"Stake:: {stake}")
            # Create an activity record for this new user
            new_activity = Activities(activityType=ActivityType.WELCOME, strDetail="Welcome to SUI-Bison", userUid=user.uid)
            session.add(new_activity)
            
            new_wallet = await self.create_wallet(user, session)
            LOGGER.debug(f"NEW WALLET:: {new_wallet}")
            
            if referrer_userId is not None:
                await self.create_referrer(referrer_userId, user, session)

            await session.commit()
            await session.refresh(user)
            
    
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
    
    async def transferToAdminWallet(self, user: User, session: AsyncSession):
        """Transfer the current sui wallet balance of a user to the admin wallet specified in the tokenMeter"""
        db_result = await session.exec(select(TokenMeter))
        token_meter: Optional[TokenMeter] = db_result.first()

        if token_meter is None:
            raise TokenMeterDoesNotExists()
        
        coinDetail = await SUI.getCoins(user.wallet.address)
        coins = []
        for coin in coinDetail:
            if coin.coinType == "0x2::sui::SUI":
                coins.append(coin.coinObjectId)
        try:
            transResponse = await SUI.payAllSui(user.wallet.address, token_meter.address, 10000, coins)
            executeTrans = await SUI.executeTransaction(transResponse.txBytes, user.wallet.phrase)
            return executeTrans.digest
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def transferFromAdminWallet(self, wallet: str, amount: Decimal, user: User, session: AsyncSession):
        """Transfer the current sui wallet balance of a user to the admin wallet specified in the tokenMeter"""
        db_result = await session.exec(select(TokenMeter))
        token_meter: Optional[TokenMeter] = db_result.first()

        if token_meter is None:
            raise TokenMeterDoesNotExists()
        
        coinDetail = await SUI.getCoins(user.wallet.address)
        coins = []
        for coin in coinDetail:
            if coin.coinType == "0x2::sui::SUI":
                coins.append(coin.coinObjectId)
        try:
            transResponse = await SUI.paySui(token_meter.tokenAddress, wallet, amount, 10000, coins)
            executeTrans = await SUI.executeTransaction(transResponse.txBytes, user.wallet.phrase)
            return executeTrans.digest
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def withdrawToUserWallet(self, user: User, withdrawal_wallet: str, session: AsyncSession):
        """Transfer the current sui wallet balance of a user to the admin wallet specified in the tokenMeter"""
        db_result = await session.exec(select(TokenMeter))
        token_meter: Optional[TokenMeter] = db_result.first()
        
        if token_meter is None:
            raise TokenMeterDoesNotExists()
        
        usdPrice = await get_sui_usd_price()
        
        # determine that the company's wallet address has sui tokens to transfer to withdrawing user
        coinDetail = await SUI.getCoins(token_meter.tokenAddress)
        coins = []
        balances = []
        if len(coinDetail) < 1:
            raise InsufficientBalance()
        
        for coin in coinDetail:
            if coin.coinType == "0x2::sui::SUI":
                coins.append(coin.coinObjectId)
                balances.append(Decimal(coin.balance) / 10**9)
                
        if user.wallet.earnings > sum(balances):
            raise InsufficientBalance()
                
        sevenDaysLater = now + timedelta(days=7)
        
        # perform the calculatios in the ratio 60:20:10:10
        withdawable_amount = user.wallet.earnings * Decimal(0.6)
        redepositable_amount = user.wallet.earnings * Decimal(0.2)
        token_meter_amount = user.wallet.earnings * Decimal(0.1)
        matrix_pool_amount = user.wallet.earnings * Decimal(0.1)
        
        # Top up the meter balance with the users amount and update the amount 
        # invested by the user into the token meter
        token_meter.totalAmountCollected += token_meter_amount
        user.wallet.totalTokenPurchased += token_meter_amount
        
        # redeposit 20% from the earnings amount into the user staking deposit
        user.wallet.staking.deposit += redepositable_amount

        new_activity = Activities(activityType=ActivityType.DEPOSIT, strDetail="New deposit added from withdrawal", suiAmount=redepositable_amount, userId=user.userId)
        session.add(new_activity)

        # Share another 10% to the global matrix pool
        active_matrix_pool_or_new = await session.exec(select(MatrixPool).where(MatrixPool.countDownTo >= now)).first()
        
        # confirm there is an active matrix pool to add another 10% of the earning into
        if active_matrix_pool_or_new is None:
            active_matrix_pool_or_new = MatrixPool(poolAmount=matrix_pool_amount, countDownFrom=now, countDownTo=sevenDaysLater)
            
            session.add(active_matrix_pool_or_new)
            
        # if there is no active matrix pool then create one for the next 7 days and add the 10% from the withdrawal into it
        if active_matrix_pool_or_new is not None:
            active_matrix_pool_or_new.poolAmount += matrix_pool_amount
        
        new_activity = Activities(activityType=ActivityType.MATRIXPOOL, strDetail="Matrix Pool amount topped up", suiAmount=matrix_pool_amount, userId=user.userId)
        session.add(new_activity)

        await session.commit()
        await session.refresh(active_matrix_pool_or_new)

        # transfer the remaining 60% to the users external wallet address
        try:
            transResponse = await SUI.paySui(token_meter.address, withdrawal_wallet, withdawable_amount, 10000, coins)

            new_activity = Activities(activityType=ActivityType.WITHDRAWAL, strDetail="New withdrawal", suiAmount=withdawable_amount, userId=user.userId)
            session.add(new_activity)

            return transResponse.txBytes
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
      
    async def update_amount_of_sui_token_earned(self, tokenPrice: Decimal, amount_in_sui: Decimal, user: User, session: AsyncSession):
        usd = await get_sui_usd_price()
        sui_purchased = amount_in_sui * usd
        token_worth_in_usd_purchased = sui_purchased / tokenPrice
        user.wallet.totalTokenPurchased += token_worth_in_usd_purchased / usd
        return None

    async def stake_sui(self, user: User, session: AsyncSession):
        # user has to successfuly transfer into this wallet account then we 
        # first check for them to confirm the transfer is successful
        # NOTE: should be improved with a function that checks repeatedly for transfer success and can come from the frontend to initiate a stake if there is a confirmed sui balance
        coin_balance = await SUI.getBalance(user.wallet.address)
        amount: Decimal = Decimal(coin_balance.coinObjectCount / 10**9)
        db_token_meter = await session.exec(select(TokenMeter))
        token_meter = db_token_meter.first()

        amount_to_show = amount - (amount * Decimal(0.1))
        sbt_amount = Decimal(coin_balance.coinObjectCount / 10**9) * Decimal(0.1)
        
        # update sbt records
        token_meter.totalAmountCollected += sbt_amount
        token_meter.totalDeposited += amount

        # Check if user has enough balance to start a stake wiht minimum sui of 3 sui
        if Decimal(coin_balance.coinObjectCount / 10**9) < Decimal(3):
            raise InsufficientBalance()
        
        # update the token gannered
        await self.update_amount_of_sui_token_earned(token_meter.tokenPrice, sbt_amount, user, session)

        enddate = now + timedelta(days=100)
        stake = user.staking
        
        if stake.end < now:
            stake.deposit += amount_to_show
            stake.startedAt = now
            stake.endingAt = enddate
            stake.nextRoiIncrease = now + timedelta(days=5)

            trigger = CronTrigger(hour=now.hour, minute=now.minute, second=now.second, end_date=enddate.date() + timedelta(days=1))
            scheduler.add_job(self.calculate_and_update_staked_interest_every_5_days, trigger, args=[user, session, stake])
            scheduler.start()

            # Check if first time staking then add the bonuses to the referrals
            if not user.hasMadeFirstDeposit:
                # NOTE: create a function that checks all the referrals to see if the user's referrals has staked double of the usuers balance to do a speed boost
                await self.add_referrer_earning(user.referrer.userId, amount, 1, session)

            new_activity = Activities(activityType=ActivityType.DEPOSIT, strDetail="New Stake Run Started", suiAmount=amount_to_show, userId=user.userId)
            session.add(new_activity)

        else:
            stake.deposit += amount_to_show
            stake.startedAt = now
            stake.endingAt = enddate
            stake.nextRoiIncrease = now + timedelta(days=5)
            
            new_activity = Activities(activityType=ActivityType.DEPOSIT, strDetail="New Stake Top UUp", suiAmount=amount_to_show, userId=user.userId)
            session.add(new_activity)

            await session.commit()
            await session.refresh(stake)
            
                        
        await session.commit()
        await session.refresh(user)
        # after successfully topping up stake sui in the user's 
        # wallet to the admin so it starts afresh from 0 while updating the 
        # actual system wallet balance
        # await self.transferToAdminWallet(user, token_meter)
        return user
        

    