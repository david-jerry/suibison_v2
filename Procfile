web: gunicorn -k uvicorn.workers.UvicornWorker main:app
telegram: python telegram_bot.py
celery_beat: celery -A src.celery_tasks.celery_app beat --loglevel=INFO
celery_worker: celery -A src.celery_tasks.celery_app worker --loglevel=INFO -E