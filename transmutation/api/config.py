"""Configuration loader"""
# go to .env to modify configuration variables or use environment variables
from pydantic import BaseSettings
from typing import Optional
import os.path
import logging
import logging.config
from fastapi.logger import logger as fastapi_logger


class Settings(BaseSettings):
    app_name: str = "Transmutation API"
    google_api_key: str
    google_cx: str
    bing_api_key: str | None
    bing_customconfig: str | None
    log_file: str | None
    redis_username: Optional[str]
    redis_password: str
    redis_host: str
    redis_port: str
    cache_redis_db: int
    cache_expiration: int
    celery_redis_db: int
    server_port: int
    api_keys: list[str]
    api_key_name: str
    log_config: str
    bulk_size: int

    class Config:
        env_file = ".env"

settings = Settings()

# deal with fastapi issue with root/module loggers
# see https://github.com/tiangolo/uvicorn-gunicorn-fastapi-docker/issues/19
# with open(os.path.join(os.path.dirname(__file__),settings.log_config)) as f:
#    log_config = yaml.safe_load(f)
# logging.config.dictConfig(log_config)
# create logger
log = logging.getLogger(__name__)

# This way, if your app is loaded via gunicorn, you can tell the logger to use gunicorn's log level instead of the default one.
# Because if gunicorn loads your app, FastAPI does not know about the environment variable directly;
# you will have to manually override the log level.

gunicorn_error_logger = logging.getLogger("gunicorn.error")
gunicorn_logger = logging.getLogger("gunicorn")
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.handlers = gunicorn_error_logger.handlers

fastapi_logger.handlers = gunicorn_error_logger.handlers

fastapi_logger.setLevel(gunicorn_logger.level)
