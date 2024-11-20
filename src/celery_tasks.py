import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Annotated
from celery import Celery
from celery.schedules import crontab
from fastapi import Depends
from src.celery_beat import TemplateScheduleSQLRepository
from src.config.settings import Config
from src.db.engine import get_session
from src.utils.logger import LOGGER

from sqlmodel.ext.asyncio.session import AsyncSession

db_dependency = Annotated[AsyncSession, Depends(get_session)]
celery_beat = TemplateScheduleSQLRepository()

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

# run the task to fetch sui price every hour(3600 seconds) and store in the redis database
celery_app.conf.beat_schedule = {
    "fetch_sui_usd_price_hourly": {
        "task": "fetch_sui_usd_price_hourly",
        "schedule": 3660,
    },
    # 'update_user_balances_every_hour': {
    #     'task': 'update_user_balances',
    #     'schedule': crontab(minute='0', hour='*'),
    # },
}



@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, session: db_dependency, **kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        await_tasks = loop.run_forever(celery_beat.get_periodic_taskks(session))
        tasks = await_tasks
        
        for task in tasks:
            crondict = json.loads(task.crontab)
            celery_app.conf.beat_schedule[task.task_name] = {
                "task": task.task_name,
                "schedule": crontab(**crondict),
                "args": (arg for arg in task.task_args),
            }
        
        LOGGER.debug("Periodic tasks configured successful")
    except Exception as e:
        LOGGER.error(f"Error setting the periodic tasks")
        raise
        
