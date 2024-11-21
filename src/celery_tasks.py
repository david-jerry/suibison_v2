import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Annotated
from celery import Celery
from celery.schedules import crontab
from fastapi import Depends
# from src.celery_beat import TemplateScheduleSQLRepository
from src.config.settings import Config
from src.db import engine
from src.utils.logger import LOGGER

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

# celery_beat = TemplateScheduleSQLRepository()

# Initialize Celery with autodiscovery
celery_app = Celery(
    "sui-byson",
    broker=Config.CELERY_BROKER_URL,
)
celery_app.config_from_object(Config)
celery_app.conf.result_backend = Config.RESULT_BACKEND
celery_app.conf.enable_utc = True
celery_app.conf.timezone = "UTC"
celery_app.conf.task_serializer='json'
celery_app.conf.result_serializer='json'
celery_app.conf.broker_connection_retry_on_startup = True

# Autodiscover tasks from all installed apps (each app should have a 'tasks.py' file)
celery_app.autodiscover_tasks(packages=['src.apps.accounts'], related_name='tasks')

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_post_celery_config())
    
async def run_post_celery_config():
    celery_app.add_periodic_task(
        schedule=crontab(minute="0", hour="*"),
        name="fetch_sui_usd_price_hourly",
        sig=celery_app.signature("fetch_sui_usd_price_hourly") 
    ) #fetch_sui_usd_price_hourly.s()

    # Session = sessionmaker(
    #     bind=engine,
    #     class_=AsyncSession,
    #     expire_on_commit=False,
    #     autoflush=False,
    # )
    
    # try:
    #     async with Session() as session:
    #         # await_tasks = await celery_beat.get_periodic_taskks(session)
    #         # tasks = await_tasks
            
    #         # for task in tasks:
    #             # crondict = json.loads(task.crontab)
    #             # celery_app.add_periodic_task(
    #             #     schedule=crontab(**crondict),
    #             #     name=task.task_name,
    #             #     sig=celery_app.signature(task.task_sig),
    #             #     args=(arg for arg in task.task_args)
    #             # )
    #             # celery_app.conf.beat_schedule[task.task_name] = {
    #             #     "task": task.task_name,
    #             #     "schedule": crontab(**crondict),
    #             #     "args": (arg for arg in task.task_args),
    #             # }
            
    #     LOGGER.debug("Periodic tasks configured successful")
    # except Exception as e:
    #     LOGGER.error(f"Error setting the periodic tasks")
        
        
