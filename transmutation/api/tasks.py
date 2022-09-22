"""Background Tasks management using Celery"""

import os
import time

# config
from .config import settings
from .config import log

from celery import Celery
from celery.result import AsyncResult

credentials = str()
if settings.redis_username:
    credentials += settings.redis_username
    if settings.redis_password:
        credentials += f":{settings.redis_password}"
    credentials += "@"
broker = backend = f"redis://{credentials}{settings.redis_host}:{settings.redis_port}/{settings.celery_redis_db}"
tasks_celery = Celery(__name__, broker=broker, backend=backend)
task = tasks_celery.task