import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated
from celery import shared_task
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession
import ast
from telegram import User
import yfinance as yf

from src.apps.accounts.models import TokenMeter
from src.celery_tasks import celery_app
from src.db.engine import get_session
from src.db.redis import redis_client
from src.utils.logger import LOGGER
from sqlmodel import select

@celery_app.task(name="fetch_dollar_price")
def fetch_sui_usd_price_hourly():
    # fetch dollar rate from oe sui to check agaist the entire website
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    future = loop.run_until_complete(fetch_sui_price())
    loop.close()
    # asyncio.run(fetch_sui_price())


async def fetch_sui_price():
    sui = yf.Ticker("SUI20947-USD")
    rate = sui.fast_info.last_price
    LOGGER.debug(f"SUI Price: {rate}")
    await redis_client.set("sui_price", rate)

    # # Use `get_session` to manage the session lifecycle
    # async with get_session() as session:
    #     # Fetch the token data
    #     token_result = await session.exec(select(TokenMeter))
    #     token = token_result.first()

    #     if token is None:
    #         # Create a new TokenMeter entry
    #         new_token = TokenMeter(suiUsdPrice=Decimal(rate))
    #         session.add(new_token)
    #         await session.commit()
    #         LOGGER.info("Created new TokenMeter entry with SUI price.")
    #     else:
    #         # Update the existing TokenMeter entry
    #         token.suiUsdPrice = Decimal(rate)
    #         await session.commit()
    #         await session.refresh(token)
    #         LOGGER.info("Updated TokenMeter entry with new SUI price.")
