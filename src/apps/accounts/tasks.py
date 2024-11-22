import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
import pprint
from typing import Annotated
from celery import shared_task
from fastapi import Depends

from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

import ast

from src.apps.accounts.models import TokenMeter, User, UserReferral, UserStaking, UserWallet
import yfinance as yf

from src.apps.accounts.services import UserServices
from src.celery_tasks import celery_app
from src.db import engine
from src.db.engine import get_session, get_session_context
from src.db.redis import redis_client
from src.utils.calculations import get_rank
from src.utils.logger import LOGGER
from sqlmodel import select

user_services = UserServices()
session = Annotated[AsyncSession, Depends(get_session)]

@celery_app.task(name="fetch_sui_usd_price_hourly")
def fetch_sui_usd_price_hourly():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_sui_price())
    loop.close()
    
@celery_app.task(name="check_and_update_balances")
def check_and_update_balances():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_sui_balance())
    loop.close()
                
@celery_app.task(name="run_calculate_daily_tasks")
def run_calculate_daily_tasks():    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(calculate_daily_tasks())
    loop.close()



async def fetch_sui_price():
    sui = yf.Ticker("SUI20947-USD")
    rate = sui.fast_info.last_price
    LOGGER.debug(f"SUI Price: {rate}")
    await redis_client.set("sui_price", rate)
    
async def fetch_sui_balance():
    async with get_session_context() as session:
        user_db = await session.exec(select(User).where(User.isBlocked == False))
        users = user_db.all()
        
        for user in users:
            user_services.stake_sui(user, session)

async def calculate_daily_tasks():
    now = datetime.now()
    async with get_session_context() as session:
        user_db = await session.exec(select(User).where(User.isBlocked == False))
        users = user_db.all()
        
        for user in users:
            # ######### CALCULATTE RANK EARNING ########## #
            
            db_result = await session.exec(select(UserReferral).where(UserReferral.userUid == user.uid).where(UserReferral.level == 1))
            referrals = db_result.all()
            
            rankErning, rank = await get_rank(user.totalTeamVolume, user.wallet.totalDeposit, referrals)
            stake = user.staking
            
            if user.rank != rank:
                user.rank = rank
            user.wallet.weeklyRankEarnings = rankErning
            if now.date() == user.lastRankEarningAddedAt.date():
                user.wallet.earnings += Decimal(user.wallet.weeklyRankEarnings)
                user.wallet.totalRankBonus += Decimal(user.wallet.weeklyRankEarnings)
                user.wallet.expectedRankBonus += Decimal(user.wallet.weeklyRankEarnings)
                # Update lastRankEarningAddedAt to reflect the latest calculation
                user.lastRankEarningAddedAt = now + timedelta(days=7)
                
                
                
                
                
                
            # ########## CALCULATE ROI AND INTEREST ########## #
        
            # accrue interest until it reaches 4% then create the end date to be 100 days in the future
            if (stake.end is None and stake.start is not None) and (stake.roi < Decimal(0.04)) and (stake.nextRoiIncrease == now):
                # calculate interest based on remaining days and ensure the roi is less than 4%
                new_roi = stake.roi + Decimal(0.005)        
                stake.roi = new_roi        
                stake.nextRoiIncrease = now + timedelta(days=5)
            elif (stake.end is None and stake.start is not None) and stake.roi == Decimal(0.04):
                stake.end = now + timedelta(days=100)
                
            if stake.start is not None:
                interest_earned = stake.deposit * new_roi
                user.wallet.earnings += Decimal(interest_earned)                    
                    
            if stake.end.date() == now.date():
                stake.roi = Decimal(0)
                stake.end = None
                stake.nextRoiIncrease = None


            # session.add(user)
            await session.commit()
            await session.refresh(user)


























































































# @celery_app.task(name="five_day_stake_interest")
# def five_day_stake_interest():
#     # fetch dollar rate from oe sui to check agaist the entire website
    
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     loop.run_until_complete(calculate_and_update_staked_interest_every_5_days())
#     loop.close()

# async def calculate_and_update_staked_interest_every_5_days():
#     now = datetime.now()
#     async with get_session_context() as session:
#         user_db = await session.exec(select(User).where(User.isBlocked == False))
#         users = user_db.all()
        
#         for user in users:
#             stake = user.staking
            
#             remaining_days = (stake.end - now).days
            
#             # loop this task until staking expiry date has reached then stop it
#             if stake.end > now:
#                 # accrue interest until it reaches 4% then create the end date to be 100 days in the future
                    
#                 # calculate interest based on remaining days and ensure the roi is less than 4%
#                 if (stake.roi < Decimal(0.04)) and (stake.nextRoiIncrease == now):
#                     new_roi = stake.roi + Decimal(0.005)        
#                     stake.roi = new_roi        
#                     stake.nextRoiIncrease = now + timedelta(days=5)
#                 elif stake.roi == Decimal(0.04):
#                     stake.end = now + timedelta(days=100)
                    
#                 interest_earned = stake.deposit * new_roi
#                 user.wallet.earnings += interest_earned                    
#                 user.wallet.earnings += (stake.deposit * stake.roi)
                    
#             if stake.end < now:
#                 stake.roi = 0.01
#                 stake.nextRoiIncrease = None
                
#             await session.commit()
#             await session.refresh(stake)
#             return None
    


