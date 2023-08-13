"""Configuration loader"""
# go to .env to modify configuration variables or use environment variables
from typing import Optional
import requests
from random import choice

from loguru import logger as log

from redis.asyncio import Redis
from pydantic_settings import BaseSettings, SettingsConfigDict

NITTER_INSTANCES = "https://status.d420.de/api/v1/instances"
NITTER_BACKUP_INSTANCE = "https://nitter.net"
PUBLIC_EMAIL_PROVIDERS_URL = "https://raw.githubusercontent.com/ankaboot-source/email-open-data/main/public-email-providers.json"
JOBTITLES_FILE = "miners/jobtitles.json"


def pick_nitter_instance(
    instances_url=NITTER_INSTANCES,
    backup_instance=NITTER_BACKUP_INSTANCE,
    timeout=3,
    min_points=50,
    first=5
) -> str:
    instance = ""
    try:
        instances = {
            instance["ping_avg"]: instance["url"]
            for instance in requests.get(instances_url, timeout=timeout).json()["hosts"]
            if instance["points"] > min_points and instance['ping_avg']
        }
        instance = instances[choice(sorted(instances.keys())[:first])]
    except requests.RequestException:
        log.warning(f"Failure to get nitter instances, fallback to {backup_instance}")
        instance = backup_instance
    return instance


def get_public_email_providers(public_email_providers_url=PUBLIC_EMAIL_PROVIDERS_URL) -> set[str]:
    public_email_providers = set()
    try:
        public_email_providers = set(requests.get(public_email_providers_url).json())
    except requests.RequestException as e:
        log.error(f"Impossible to GET {public_email_providers_url}: {e}")
    return public_email_providers


class Settings(BaseSettings):
    app_name: str = "Transmutation API"
    google_api_key: str
    google_cx: str
    google_vision_credentials: str
    query_type: str = "q"
    bing_api_key: Optional[str] = None
    bing_customconfig: Optional[str] = None
    log_level: Optional[str] = None
    log_filepath: Optional[str] = None
    redis_username: Optional[str] = None
    redis_password: Optional[str] = None
    redis_host: str
    redis_port: str
    cache_redis_db: int
    cache_expiration: int
    server_port: int
    api_keys: list[str]
    api_key_name: str
    google_vision_credentials: str
    public_email_providers: Optional[set[str]] = get_public_email_providers()
    jobtitles_list_file: str = JOBTITLES_FILE
    nitter_instance_server: str = pick_nitter_instance()
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


async def setup_cache(settings: Settings, db: int) -> Redis:
    """setup cache based on Redis

    Args:
        settings (Settings):settings including redis_*
        db (int): database

    Returns:
        redis: redis database instance
    """
    # redis parameters
    redis_parameters = {
        setting_k.removeprefix("redis_"): setting_v
        for setting_k, setting_v in settings.model_dump().items()
        if setting_k.startswith("redis")
    }
    redis_parameters["db"] = db
    redis_parameters["decode_responses"] = True
    redis_parameters["encoding"] = "utf-8"
    cache = await Redis(**redis_parameters)
    log.info(f"Set-up redis cache for {db}")
    return cache
