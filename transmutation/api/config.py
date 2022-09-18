"""Configuration loader"""
# go to .env to modify configuration variables or use environment variables
import yaml
from pydantic import BaseSettings
from typing import Optional
import os.path

class Settings(BaseSettings):
    app_name: str = "Transmutation API"
    google_api_key: str
    google_cx: str
    bing_api_key: str
    bing_customconfig: str
    log_file: str
    redis_username: Optional[str]
    redis_password: str
    redis_host: str
    redis_port: str
    redis_db: str
    cache_expiration: int
    server_port: int
    api_keys: list[str]
    api_key_name: str
    log_config: str

    class Config:
        env_file = ".env"

settings = Settings()

with open(os.path.join(os.path.dirname(__file__),settings.log_config)) as f:
    log_config = yaml.safe_load(f)

# deal with fastapi issue with root/module loggers
# see https://github.com/tiangolo/uvicorn-gunicorn-fastapi-docker/issues/19
import logging.config

logging.config.dictConfig(log_config)
# create logger
log = logging.getLogger(__name__)