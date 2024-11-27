import asyncio
from decimal import Decimal
import json
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

import requests
from sqlalchemy import Date, cast
from sqlmodel import select, func, literal
from sqlmodel.ext.asyncio.session import AsyncSession

from src.apps.accounts.dependencies import user_exists_check
from src.apps.accounts.enum import ActivityType
from src.apps.accounts.models import Activities, MatrixPool, MatrixPoolUsers, PendingTransactions, TokenMeter, User, UserReferral, UserStaking, UserWallet
from src.apps.accounts.schemas import AdminLogin, AllStatisticsRead, MatrixUserCreateUpdate, TokenMeterCreate, TokenMeterUpdate, UserCreateOrLoginSchema, UserLoginSchema, UserUpdateSchema, Wallet
from src.celery_beat import TemplateScheduleSQLRepository
from src.utils.calculations import get_rank
from src.utils.sui_json_rpc_apis import SUI
from src.errors import ActivePoolNotFound, InsufficientBalance, InvalidCredentials, InvalidStakeAmount, InvalidTelegramAuthData, OnlyOneTokenMeterRequired, ReferrerNotFound, StakingExpired, TokenMeterDoesNotExists, TokenMeterExists, UserAlreadyExists, UserBlocked, UserNotFound
from src.utils.hashing import createAccessToken, verifyHashKey, verifyTelegramAuthData
from src.utils.logger import LOGGER
from src.config.settings import Config
from src.db.redis import get_sui_usd_price


from mnemonic import Mnemonic
from bip_utils import Bip39EntropyBitLen, Bip39EntropyGenerator, Bip39MnemonicGenerator, Bip39WordsNum, Bip39Languages
from cryptography.hazmat.primitives.asymmetric import ed25519
from sui_python_sdk.wallet import SuiWallet

now = datetime.now()
celery_beat = TemplateScheduleSQLRepository()

STAKING_MIN = 1


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
                userId=poolUser.userId,
                referralsAdded=poolUser.referralsAdded
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
            transactions = await session.exec(select(Activities).where(Activities.activityType == ActivityType.DEPOSIT, Activities.activityType == ActivityType.WITHDRAWAL).where(Activities.created.date() >= date).order_by(Activities.created))
            return transactions.all()
        transactions = await session.exec(select(Activities).where(Activities.activityType == ActivityType.DEPOSIT, Activities.activityType == ActivityType.WITHDRAWAL).order_by(Activities.created))
        return transactions.all()

    async def getAllActivities(self, date: Optional[date], session: AsyncSession):
        if date is not None:
            allActivities = await session.exec(select(Activities).where(Activities.created >= now).order_by(Activities.created))
            return allActivities.all()
        allActivities = await session.exec(select(Activities).order_by(Activities.created))
        return allActivities.all()


    async def getAllUsers(self, date: date, session: AsyncSession):
        if date is not None:
            users: Page[User] = await paginate(session, select(User).where(User.isSuperuser == False).where(User.joined.date() >= date).order_by(User.joined, User.firstName))
            return users
        users = await paginate(session, select(User).where(User.isSuperuser == False).order_by(User.joined, User.firstName))
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
    # #####  WORKING ENDOINT
    async def sui_wallet_endpoint(self, url: str, body: Optional[dict]):
        headers = {
            "accept": "*/*",
            "Content-Type": "application/json"
        }

        LOGGER.debug(body)

        response = requests.post(url, headers=headers, json=body)
        LOGGER.debug(response.json())
        result = response.json()
        if 'error' in result:
            raise Exception(f"Error: {result['error']}")
        res = result
        LOGGER.debug(res)
        return res


    async def get_user_downlines(self, user: User, level: int, session: AsyncSession):
        cte = (
            select(
                User.uid.label("uid"),
                User.userId.label("userId"),
                User.firstName.label("firstName"),
                User.referrer_id.label("referrer_id"),
                literal(1).label("level"),
            )
            .where(User.referrer_id == user.uid)
            .cte(recursive=True)
        )

        cte = cte.union_all(
            select(
                User.uid,
                User.userId,
                User.firstName,
                User.referrer_id,
                (cte.c.level + 1).label("level"),
            ).join(User, User.referrer_id == cte.c.uid)
        )

        query = (
            select(User)
            .join(cte, User.uid == cte.c.uid)
            .where(cte.c.level == level)
        )

        results = await session.exec(query)
        return results.all()

    async def create_referral_level(self, new_user: User, referring_user: User, level: int, session: AsyncSession):
        referrer = referring_user
        if level < 20:
            referrer.totalNetwork += 1
            referrer.totalReferrals += 1 if level == 1 else 0

            name = f"{referring_user.userId} Referral"
            if new_user.firstName:
                name = f"{new_user.firstName}"

            new_referral = UserReferral(
                level=level,
                name=name,
                reward=Decimal(0.00),
                theirUserId=new_user.userId,
                userUid=new_user.uid,
                userId=referrer.userId,
            )
            session.add(new_referral)
            if level == 1:
                session.add(Activities(activityType=ActivityType.REFERRAL, strDetail=f"New Level {level} referral added", userUid=referrer.uid))
            await session.commit()

            if new_referral is not None:
                LOGGER.debug(f"New Referral for {referrer.userId}: {new_referral.name}")

# ##### MOVED TO RUN IN CELRY TASK FOR EVERY 15 mins
                # # ###### ADD FAST ADD BONUS FOR THE FIRST REFERRING USER
                # if level == 1:

                #     fast_boost_time = referring_user.joined + timedelta(hours=24)
                #     db_referrals = await session.exec(select(UserReferral).where(UserReferral.userId == referring_user.userId).where(UserReferral.level == 1))
                #     referrals = db_referrals.all()

                #     paid_users = []
                #     for u in referrals:
                #         ref_db = await session.exec(select(User).where(User.userId == u.userId))
                #         referrer = ref_db.first()
                #         if referrer and referrer.staking.deposit >= Decimal(1):
                #             paid_users.append(u)

                #     if referring_user.joined < fast_boost_time and len(paid_users) >= 2:
                #         referring_user.wallet.totalFastBonus += Decimal(1.00)
                #         referring_user.staking.deposit += Decimal(1.00)

                # # ###### CHECK IF THE REFERRING USER HAS A REFERRER THEN REPEAT THE PROCESS AGAIN

            if referring_user.referrer is not None:
                db_result = await session.exec(select(User).where(User.userId == referring_user.referrer.userId))
                referrers_referrer = db_result.first()
                new_level = level + 1
                await self.create_referral_level(new_user, referrers_referrer, new_level, session)
        return None

    async def create_referrer(self, referrer_userId: Optional[str], new_user: User, session: AsyncSession):
        db_result = await session.exec(select(User).where(User.userId == referrer_userId))
        referring_user = db_result.first()

        if not referring_user:
            return

        matrix_db = await session.exec(select(MatrixPool).where(MatrixPool.endDate >= now))
        active_matrix_pool_or_new = matrix_db.first()

        if active_matrix_pool_or_new is None:
            active_matrix_pool_or_new = MatrixPool(
                totalReferrals=1,
                startDate=now,
                endDate=now + timedelta(days=7)
            )
            session.add(active_matrix_pool_or_new)
            await session.commit()
        else:
            active_matrix_pool_or_new.totalReferrals += 1

        mp_user_db = await session.exec(select(MatrixPoolUsers).where(MatrixPoolUsers.matrixPoolUid == active_matrix_pool_or_new.uid).where(MatrixPoolUsers.userId == referrer_userId))
        mp_user = mp_user_db.first()

        if mp_user is None:
            new_mp_user = MatrixPoolUsers(
                matrixPoolUid=active_matrix_pool_or_new.uid,
                userId=referrer_userId,
                referralsAdded=1,
                matrixShare=1,
            )
            session.add(new_mp_user)
            await session.commit()
        else:
            mp_user.referralsAdded += 1
            mp_user.matrixShare += 1

        await session.commit()

        new_user.referrer_id = referring_user.uid
        await session.commit()

        await self.create_referral_level(new_user, referring_user, 1, session)

        # check for fast boost and credit the users wallet balance accordingly
        return None

    async def create_wallet(self, user: User, session: AsyncSession):
        # mnemonic_phrase = Mnemonic("english").generate(strength=128)
        mnemonic_phrase = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)
        url = "https://suiwallet.sui-bison.live/wallet"

        res = await self.sui_wallet_endpoint(url, None)
        LOGGER.debug(res)

        my_wallet = Wallet(**res)
        my_address = my_wallet.address
        my_private_key = my_wallet.privateKey

        # Save the new wallet in the database
        new_wallet = UserWallet(address=my_address, phrase=mnemonic_phrase.ToStr(),
                                privateKey=my_private_key, userUid=user.uid)
        session.add(new_wallet)
        return new_wallet

    async def create_staking_account(self, user: User, session: AsyncSession):
        # Create a new staking account for the user wallet to store their staking details
        new_staking = UserStaking(userUid=user.uid)
        LOGGER.debug(f"NEW_STAKING:: {new_staking}")
        session.add(new_staking)
        return new_staking

    async def authenticate_user(self, form_data: AdminLogin, session):
        user = await user_exists_check(form_data.userId, session)

        if user is None:
            raise UserNotFound()

        valid_password = verifyHashKey(form_data.password, user.passwordHash)
        if not valid_password:
            raise InvalidCredentials()

        # check if the user is blocked
        if user is not None and user.isBlocked:
            raise UserBlocked()

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

    async def login_user(self, form_data: UserLoginSchema, session: AsyncSession) -> User:
        # validate the telegram string
        if not verifyTelegramAuthData(form_data.telegram_init_data, form_data.userId):
            raise InvalidTelegramAuthData()

        user = await user_exists_check(form_data.userId, session)
        LOGGER.debug(f"User Check Found: {user}")

        if user is None:
            raise UserNotFound()

        # check if the user is blocked
        if user.isBlocked:
            raise UserBlocked()

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

    async def register_new_user(self, referrer_userId: Optional[str], form_data: UserCreateOrLoginSchema, session: AsyncSession) -> User:
        user = await user_exists_check(form_data.userId, session)
        LOGGER.debug(f"User Check Found: {user}")

        # working with existing user
        if user is not None:
            if user.isBlocked:
                raise UserBlocked()

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


        # working with new user
        new_user = User(
            userId=form_data.userId,
            firstName=form_data.firstName,
            lastName=form_data.lastName,
            phoneNumber=form_data.phoneNumber,
            image=form_data.image,
            isAdmin=False,
        )
        session.add(new_user)

        if referrer_userId is not None:
            LOGGER.info(f"CREATING A NEW REFERRAL FOR: {referrer_userId}")
            await self.create_referrer(referrer_userId, new_user, session)

        stake = await self.create_staking_account(new_user, session)
        LOGGER.debug(f"Stake:: {stake}")

        # Create an activity record for this new user
        new_activity = Activities(activityType=ActivityType.WELCOME, strDetail="Welcome to SUI-Bison", userUid=new_user.uid)
        session.add(new_activity)

        new_wallet = await self.create_wallet(new_user, session)
        LOGGER.debug(f"NEW WALLET:: {new_wallet}")

        await session.commit()
        await session.refresh(new_user)

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

        db_res = await session.exec(select(UserReferral).where(UserReferral.user == user))
        the_referred_user = db_res.first()
        if the_referred_user is not None:
            the_referred_user.name = f"{form_data.firstName} {form_data.lastName}" if form_data.firstName or form_data.lastName else the_referred_user.name

        await session.commit()
        await session.refresh(user)
        return user

    async def getUserActivities(self, user: User, session: AsyncSession):
        query = select(Activities).where(Activities.userUid == user.uid).order_by(Activities.created).limit(25)
        db = await session.exec(query)
        allActivities = db.all()
        return allActivities

    async def update_amount_of_sui_token_earned(self, tokenPrice: Decimal, amount_in_sui: Decimal, user: User, session: AsyncSession):
        usd = await get_sui_usd_price()
        sui_purchased = amount_in_sui * usd
        token_worth_in_usd_purchased = sui_purchased / tokenPrice
        user.wallet.totalTokenPurchased += token_worth_in_usd_purchased
        return None

    async def calc_team_volume(self, referrer: User, amount: Decimal, level: int, session: AsyncSession):
        LOGGER.info(F"Debuggin here::::: {amount} {level} {referrer}")
        if level < 6:
            referrer.totalTeamVolume += amount
            await session.commit()
            if referrer.referrer:
                level_referrer_db = await session.exec(select(User).where(User.userId == referrer.referrer.userId))
                level_referrer = level_referrer_db.first()
                await self.calc_team_volume(level_referrer, amount, level + 1, session)
        return None

    async def transferToAdminWallet(self, user: User, amount: Decimal, session: AsyncSession):
        """Transfer the current sui wallet balance of a user to the admin wallet specified in the tokenMeter"""
        db_result = await session.exec(select(TokenMeter))
        token_meter: Optional[TokenMeter] = db_result.first()
        LOGGER.info(F"AMOUNT TO SEND TO ADMIN: {amount}")
        t_amount = round(amount * Decimal(10**9))
        LOGGER.debug(f"FORMATTED AMOUNT: {t_amount}")

        if token_meter is None:
            raise TokenMeterDoesNotExists()

        try:
            status = await self.performTransactionToAdmin(token_meter.tokenAddress, user.wallet.address, user.wallet.privateKey )
            if "failure" in status:
                LOGGER.debug(f"RETRYING REANSFER")
                t_amount -= 100
                self.transferToAdminWallet(user, Decimal(t_amount / 10**9), session)
            return status
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def performTransactionToAdmin(self, recipient: str, sender: str, privKey: str) -> str:
        coinIds = await SUI.getCoins(sender)
        transferResponse = await SUI.payAllSui(sender, recipient, Decimal(0.005), coinIds)
        transaction = await SUI.executeTransaction(transferResponse.txBytes, privKey)
        return transaction

    async def performTransactionFromAdmin(self, amount: Decimal, recipient: str, sender: str, privKey: str) -> str:
        coinIds = await SUI.getCoins(sender)
        transferResponse = await SUI.paySui(sender, recipient, amount, Decimal(0.005), coinIds)
        transaction = await SUI.executeTransaction(transferResponse.txBytes, privKey)
        return transaction

    async def handle_stake_logic(self, amount: Decimal, token_meter: TokenMeter, user: User, session: AsyncSession):
        LOGGER.debug(f"FIRST CHECK PASS? : {Decimal(0.00500000) < amount}")
        LOGGER.debug(f"SECOND CHECK PASS? : {Decimal(0.000000000) < amount < Decimal(0.9)}")
        LOGGER.debug(f"THIRD CHECK PASS? : {Decimal(0.0050000000) <= amount}")

        """Core logic for handling the staking process."""
        amount_to_show = amount - Decimal(amount * Decimal(0.1))
        sbt_amount = amount * Decimal(0.1)

        token_meter.totalAmountCollected += sbt_amount
        token_meter.totalDeposited += amount
        user.staking.deposit += amount_to_show

        await self.update_amount_of_sui_token_earned(token_meter.tokenPrice, sbt_amount, user, session)

        enddate = now + timedelta(days=100)
        stake = user.staking

        # if there is a top up or new stake balance then run else just skip
        if stake.end is None:
            stake.start = now
            stake.end = enddate
            stake.nextRoiIncrease = now + timedelta(days=5)

            new_activity = Activities(activityType=ActivityType.DEPOSIT,
                                    strDetail="New Stake Run Started", suiAmount=amount_to_show, userUid=user.uid)

            session.add(new_activity)

        else:
            new_activity = Activities(activityType=ActivityType.DEPOSIT, strDetail="Stake Top Up",
                                    suiAmount=amount_to_show, userUid=user.uid)
            session.add(new_activity)

        LOGGER.debug(f"OKay got here. Debugging transfer call")
        transactionData = await self.transferToAdminWallet(user, amount, session)
        if "failure" in transactionData:
            raise HTTPException(status_code=400, detail=f"There was a transfer failure with this transaction: {transactionData}")

    async def _get_user_balance(self, wallet_address: str):
        try:
            url = "https://suiwallet.sui-bison.live/wallet/balance"
            body = {
                "address": wallet_address
            }
            res = await self.sui_wallet_endpoint(url, body)
            balance = Decimal(Decimal(res["balance"]) / 10**9)
            LOGGER.debug(f"BAl Check: {balance} - {wallet_address}")
            return balance
        except Exception:
            return None

    async def _clear_pending_deposit(self, user: User, pendingBalance: Decimal):
        LOGGER.debug(f"Looker at 100")
        user.wallet.balance -= pendingBalance
        user.wallet.totalDeposit -= pendingBalance
        user.wallet.pendingBalance = 0

    async def _update_user_balance(self, user: User, amount: Decimal, session: AsyncSession):
        LOGGER.debug(f"Looker at 1")
        if amount >= STAKING_MIN:
            LOGGER.debug(f"Looker at 2")
            if user.wallet.pendingBalance > 0:
                LOGGER.debug(f"Looker at 3")
                self._clear_pending_deposit(user, user.wallet.pendingBalance)

        LOGGER.debug(f"Looker at 4")
        if amount < STAKING_MIN:
            LOGGER.debug(f"Looker at 5")
            user.wallet.pendingBalance += amount

        LOGGER.debug(f"Looker at 6")
        user.wallet.totalDeposit += amount
        user.wallet.balance += amount

    async def stake_sui(self, user: User, session: AsyncSession):
        LOGGER.debug(f"Got here 1:::: {user.firstName} {user.userId} {user.uid} -- {user.referrer_id} - {user.referrer.userUid if user.referrer else None} {user.referrer.userId if user.referrer else None}")
        deposit_amount = await self._get_user_balance(user.wallet.address)

        if not deposit_amount:
            return

        LOGGER.debug(f"Got here 2")

        try:
            await self._update_user_balance(user, deposit_amount, session)

            LOGGER.debug(f"Got here 3")

            if deposit_amount < STAKING_MIN:
                LOGGER.debug(f"Got here 4")
                await session.commit()
                await session.refresh(user)
                return

            LOGGER.debug(f"Got here 5")

            # get ttoken meter details
            db_token_meter = await session.exec(select(TokenMeter))
            token_meter = db_token_meter.first()

            if token_meter is None:
                raise TokenMeterDoesNotExists()

            LOGGER.debug(f"Got here 6")

            # perform stake calculations
            try:
                await self.handle_stake_logic(deposit_amount, token_meter, user, session)
                LOGGER.debug(f"Got here 7")
            except Exception as e:
                LOGGER.debug(f"Got here 8")
                raise HTTPException(status_code=400, detail="Staking Failed")

            LOGGER.debug(f"Got here 9")
            if user.referrer_id:
                db_result = await session.exec(select(User).where(User.uid == user.referrer_id))
                user_referrer = db_result.first()

                LOGGER.debug(f"Got here 10. Referrer name: {user_referrer.userId}")
                # if not user.hasMadeFirstDeposit:
                await self.add_referrer_earning(user, user_referrer.userId, deposit_amount, 1, session)
                    # user.hasMadeFirstDeposit = True
                LOGGER.debug(f"USER HHAS REF: {True}")
                amount_to_show = Decimal(deposit_amount - Decimal(deposit_amount * Decimal(0.1)))
 
                await self.calc_team_volume(user_referrer, amount_to_show, 1, session)

            LOGGER.debug(f"Got here 11")

            # if user.referrer:
            #     LOGGER.debug(f"USER HHAS REF: {True}")
            #     db_res = await session.exec(select(User).where(User.userId == user.referrer.userId))
            #     referrer = db_res.first()
            #     await self.calc_team_volume(referrer, amount_to_show, 1, session)


            await session.commit()
            await session.refresh(user)
        except Exception as e:
            LOGGER.error(e)
            LOGGER.debug(f"Got here 12")
            await session.rollback()

    # ##### WORKING ENDPOINT ENDING




    # ###### TODO: CHECK FOR REASONS THE REFERRAL BONUS IS NOT WORKING

    async def add_referrer_earning(self, referral: User, referrer: Optional[str], amount: Decimal, level: int, session: AsyncSession):
        LOGGER.debug(f"executing referral earning calculations, level: {level}, referrerId: {referrer}")

        db_result = await session.exec(select(User).where(User.userId == referrer))

        referring_user = db_result.first()

        if not referring_user:
            LOGGER.debug(f"NO REFERRER TO GIVE BONUS TO")
            return None

        LOGGER.debug(f"passed user check:: {referring_user.userId}, referrer referrer: {referring_user.referrer.userId if referring_user.referrer else None}")

        # check for speed boost
        # fetch referrals for the referrer if available
        ref_db_result = await session.exec(select(UserReferral).where(UserReferral.userId == referrer))
        referrals = ref_db_result.all()
        LOGGER.debug("Fetched all referrals")

        # add referrals and their rewards
        rf_db = await session.exec(select(UserReferral).where(UserReferral.theirUserId == referral.userId).where(UserReferral.userId == referrer))
        referral_to_update = rf_db.first()

        if not referral_to_update:
            LOGGER.debug(f"NO REFERRER TO GIVE BONUS TO 2")
            return None

        # ####### Calculate Referral Bonuses
        percentage = Decimal(0.1)
        if level == 2:
            percentage = Decimal(0.05)
        elif level == 3:
            percentage = Decimal(0.03)
        elif level == 4:
            percentage = Decimal(0.02)
        elif level == 5:
            percentage = Decimal(0.01)

        LOGGER.debug(f"REFERRAL TO UPDATE: {referral_to_update.user.firstName}")
        referral_to_update.stake += amount
        referral_to_update.reward += percentage * amount

        referring_user.totalReferralsStakes += amount
        # Save the referral level down to the 5th level in redis for improved performance
        referring_user.wallet.earnings += percentage * amount
        referring_user.wallet.availableReferralEarning += percentage * amount
        referring_user.wallet.totalReferralEarnings += percentage * amount
        referring_user.wallet.totalReferralBonus += percentage * amount

        LOGGER.info(f"REFERAL EARNING FOR {referring_user.firstName if referring_user.firstName else referring_user.userId} from {referral.firstName if referral.firstName else referral.userId}: {Decimal(percentage * amount):.2f}")
        # ####### END ######### #

        ref_activity = Activities(activityType=ActivityType.REFERRAL, strDetail="Referral Bonus", suiAmount=Decimal(percentage * amount), userUid=referring_user.uid)


        # if the referrer is not none and has atleast one referral
        ref_deposit = Decimal(0.000000000)
        if referring_user.totalReferrals > Decimal(0):
            for ref in referrals:
                refd_db = await session.exec(select(User).where(User.uid == ref.userUid))
                refd = refd_db.first()
                if refd is not None:
                    ref_deposit += refd.staking.deposit

            if (ref_deposit >= (referring_user.staking.deposit * 2)) and not referring_user.usedSpeedBoost:
                referring_user.staking.roi += Decimal(0.005)
                referring_user.usedSpeedBoost = True
        # End Speed Boost

        session.add(ref_activity)

        await session.commit()

        if level <= 5 and referring_user.referrer:
            return await self.add_referrer_earning(referral, referring_user.referrer.userId, amount, level + 1, session)
        return None

    # ##### TODO:END


    async def transferFromAdminWallet(self, wallet: str, amount: Decimal, user: User, session: AsyncSession):
        """Transfer the current sui wallet balance of a user to the admin wallet specified in the tokenMeter"""
        db_result = await session.exec(select(TokenMeter))
        token_meter: Optional[TokenMeter] = db_result.first()
        t_amount = round(amount * Decimal(10**9))

        if token_meter is None:
            raise TokenMeterDoesNotExists()

        try:
            status = await self.performTransactionFromAdmin(amount, wallet, token_meter.tokenAddress, user.wallet.privateKey )
            if "failure" in status:
                LOGGER.debug(f"RETRYING REANSFER")
                t_amount -= 100
                self.transferFromAdminWallet(wallet, Decimal(t_amount / 10**9), user, session)
            return status
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def withdrawToUserWallet(self, user: User, withdrawal_wallet: str, session: AsyncSession):
        """Transfer the current sui wallet balance of a user to the admin wallet specified in the tokenMeter"""
        usdPrice = await get_sui_usd_price()
        db_result = await session.exec(select(TokenMeter))
        token_meter: Optional[TokenMeter] = db_result.first()

        if token_meter is None:
            raise TokenMeterDoesNotExists()

        # check balance
        try:
            url = "https://suiwallet.sui-bison.live/wallet/balance"
            body = {
                "address": user.wallet.address
            }
            res = await self.sui_wallet_endpoint(url, body)
            LOGGER.debug(f"BAl Check: {pprint.pprint(res)}")
            amount = Decimal(Decimal(res["balance"]) / 10**9)
            LOGGER.debug(f"User {user.userId} Balance: {amount:.9f}")
        except Exception as e:
            LOGGER.error(f"CHECK BAL: {str(e)}")
            amount = Decimal(0.000000000)

        if amount < user.wallet.earnings or user.wallet.earnings < Decimal(1):
            raise InsufficientBalance()

        sevenDaysLater = now + timedelta(days=7)

        # perform the calculatios in the ratio 60:20:10:10
        withdawable_amount = user.wallet.earnings * Decimal(0.6)
        redepositable_amount = user.wallet.earnings * Decimal(0.2)
        token_meter_amount = ((user.wallet.earnings * Decimal(0.1)) / usdPrice) / token_meter.tokenPrice
        matrix_pool_amount = user.wallet.earnings * Decimal(0.1)
        t_amount = round(withdawable_amount * Decimal(10**9)) - (1000000 + 2964000 + 978120)


        transactionData = await self.transferFromAdminWallet(withdrawal_wallet, t_amount, user, session)
        if "failure" in transactionData:
            raise HTTPException(status_code=400, detail=f"There was a transfer failure with this withdrawal: {transactionData}")

        new_activity = Activities(activityType=ActivityType.WITHDRAWAL, strDetail="New withdrawal", suiAmount=withdawable_amount, userUid=user.uid)
        session.add(new_activity)
        # Top up the meter balance with the users amount and update the amount
        # invested by the user into the token meter
        # redeposit 20% from the earnings amount into the user staking deposit
        user.wallet.totalTokenPurchased += token_meter_amount
        user.wallet.availableReferralEarning += 0.00
        user.wallet.totalWithdrawn += withdawable_amount
        user.wallet.staking.deposit += redepositable_amount
        new_activity = Activities(activityType=ActivityType.DEPOSIT, strDetail="New deposit added from withdrawal", suiAmount=redepositable_amount, userUid=user.uid)
        session.add(new_activity)

        # Share another 10% to the global matrix pool
        matrix_db = await session.exec(select(MatrixPool).where(MatrixPool.endDate >= now))
        active_matrix_pool_or_new = matrix_db.first()

        # confirm there is an active matrix pool to add another 10% of the earning into
        if active_matrix_pool_or_new is None:
            active_matrix_pool_or_new = MatrixPool(poolAmount=matrix_pool_amount, startDate=now, endDate=sevenDaysLater)
            session.add(active_matrix_pool_or_new)

        # if there is no active matrix pool then create one for the next 7 days and add the 10% from the withdrawal into it
        if active_matrix_pool_or_new is not None:
            active_matrix_pool_or_new.poolAmount += matrix_pool_amount

        token_meter.totalAmountCollected += token_meter_amount
        token_meter.totalSentToGMP += matrix_pool_amount
        token_meter.totalWithdrawn += user.wallet.earnings

        new_activity = Activities(activityType=ActivityType.MATRIXPOOL, strDetail="Matrix Pool amount topped up", suiAmount=matrix_pool_amount, userUid=user.uid)
        session.add(new_activity)

        await session.commit()
        await session.refresh(active_matrix_pool_or_new)

    # ##### UNVERIFIED ENDING



    #
