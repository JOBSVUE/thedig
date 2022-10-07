"""Configuration loader"""
# go to .env to modify configuration variables or use environment variables
from pydantic import BaseSettings
from typing import Optional

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