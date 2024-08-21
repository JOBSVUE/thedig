"""Configuration loader"""
# go to .env to modify configuration variables or use environment variables
from typing import Optional
import requests
from random import choice

from loguru import logger as log

from redis.asyncio import Redis
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import FilePath

NITTER_INSTANCES = "https://status.d420.de/api/v1/instances"
NITTER_BACKUP_INSTANCE = "https://nitter.poast.org"
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
    except (requests.RequestException, IndexError, KeyError) as e:
        log.error(f"Failure to get nitter instances {e}, fallback to {backup_instance}")
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
    app_name: str = "TheDig API"
    google_credentials: FilePath
    google_api_key: Optional[str] = None
    google_cx: Optional[str] = None
    bing_api_key: Optional[str] = None
    bing_customconfig: Optional[str] = None
    google_vertexai_projectid: Optional[str] = None
    google_vertexai_datastore: Optional[str] = None
    brave_api_key: Optional[str] = None
    github_token: Optional[str] = None
    log_level: Optional[str] = "INFO"
    log_filepath: Optional[str] = "thedig.log"
    redis_username: Optional[str] = None
    redis_password: Optional[str] = None
    redis_host: str
    redis_port: str
    cache_redis_db: int = 0
    cache_redis_db_person: int = 1
    cache_redis_db_organization: int = 2
    cache_expiration_company: int = 60*60*24*30 # 30 days
    cache_expiration_person: int = 60*60*24*1 # 1 day
    server_port: int = "8080"
    api_keys: list[str]
    api_key_name: str
    public_email_providers: Optional[set[str]] = get_public_email_providers()
    jobtitles_list_file: str = JOBTITLES_FILE
    nitter_instance_server: str = pick_nitter_instance()
    proxy: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


async def setup_cache(settings: Settings, db: Optional[int] = None) -> Redis:
    """setup cache based on Redis

    Args:
        settings (Settings):settings including redis_*
        db (int): database - Optional

    Returns:
        redis: redis database instance
    """
    # redis parameters
    redis_parameters = {
        setting_k.removeprefix("redis_"): setting_v
        for setting_k, setting_v in settings.model_dump().items()
        if setting_k.startswith("redis")
    }
    if db:
        redis_parameters["db"] = db
    redis_parameters["decode_responses"] = True
    redis_parameters["encoding"] = "utf-8"
    cache = await Redis(**redis_parameters)
    return cache
