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

from src.apps.accounts.models import TokenMeter, User, UserStaking, UserWallet
import yfinance as yf

from src.apps.accounts.services import UserServices
from src.celery_tasks import celery_app
from src.db import engine
from src.db.engine import get_session
from src.db.redis import redis_client
from src.utils.logger import LOGGER
from sqlmodel import select

user_services = UserServices()
session = Annotated[AsyncSession, Depends(get_session)]

@celery_app.task(name="fetch_sui_usd_price_hourly")
def fetch_sui_usd_price_hourly():
    # fetch dollar rate from oe sui to check agaist the entire website
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_sui_price())
    loop.close()
                
async def fetch_sui_price():
    sui = yf.Ticker("SUI20947-USD")
    rate = sui.fast_info.last_price
    LOGGER.debug(f"SUI Price: {rate}")
    await redis_client.set("sui_price", rate)



@celery_app.task(name="five_day_stake_interest")
def five_day_stake_interest():
    # fetch dollar rate from oe sui to check agaist the entire website
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_sui_price())
    loop.close()

async def calculate_and_update_staked_interest_every_5_days(self, user: User, stake: UserStaking):
    """
    This calculates and updates the interest on a stake until its expiry date.

    Args:
        session: The database session object.
        stake: The UserStaking object representing the stake.
    """
    Session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    
    now = datetime.now()
    remaining_days = (stake.end - now).days
    
    async with Session() as session:
        # loop this task until staking expiry date has reached then stop it
        if remaining_days > 0:
            # calculate interest based on remaining days and ensure the roi is less than 4%
            if (stake.roi < Decimal(0.04)) and (stake.nextRoiIncrease == now):
                new_roi = stake.roi + Decimal(0.005)        
                stake.roi = new_roi        
            interest_earned = stake.deposit * new_roi
            user.wallet.earnings += interest_earned                    
            stake.nextRoiIncrease = now + timedelta(days=5)
            user.wallet.earnings += (stake.deposit * stake.roi)
                
        if remaining_days == 0 or stake.end <= now:
            stake.roi = 0.01
            stake.nextRoiIncrease = None
            
        await session.commit()
        await session.refresh(stake)
        return None