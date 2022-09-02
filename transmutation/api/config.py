"""Configuration loader"""
# go to .env to modify configuration variables or use environment variables
from pydantic import BaseSettings
from typing import Optional

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

    class Config:
        env_file = ".env"


import yaml
with open('api/logconfig.yml') as f:
    log_config = yaml.load(f, Loader=yaml.FullLoader)
    

settings = Settings()