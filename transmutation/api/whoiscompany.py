"""Whois Company Miner API"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__copyright__ = "Ankaboot"
__license__ = "AGPL"

#service
import miners.whoiscompany as whoiscompany

#fast api
from fastapi import APIRouter
from pydantic import BaseModel
from pydantic import EmailStr
from typing import List
from typing import Dict
from api.config import Settings
from api.config import configfile  
 
settings = Settings()
router = APIRouter()

#redis
import redis
cache = redis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port, db=settings.redis_db, decode_responses=True)


#deal with fastapi issue with root/module loggers
import logging.config
logging.config.dictConfig(configfile)

#create logger
log = logging.getLogger(__name__)

@router.get("/whoiscompany/{domain}")
def whois_unique(domain: str)->str:
    company = cache.get(domain)
    #no cache for this domain
    if company is None:
        log.debug("The following domain is not cached: %s" % domain)
        company = whoiscompany.get_company(domain)
        #invalid data for this domain
        if company is None:
            log.debug("No valid data for this domain: %s" % domain)
            #redis refuse to store None so we'll use a void string instead
            company = ""
        cache.set(domain, company, ex=settings.cache_expiration)
       
    return company if company else None

@router.post("/whoiscompany")
def whois_bulk(body: Dict[str,List[str]])->dict:
    companies = {}
    for domain in body['domains']:
        company = cache.get(domain)
        if company is None:
            log.debug("The following domain is not cached: %s" % domain)
            company = whoiscompany.get_company(domain)
            if company is None:
                log.debug("No valid data for this domain: %s" % domain)
                company = ""
            cache.set(domain, company, ex=settings.cache_expiration)
        log.info(f"Domain:company - {domain}:{company}")
        companies[domain] = company if company else None
    return companies


@router.delete("/whoiscompany/cache")
def _whois_flushcache():
    """Flush cache
    """
    return cache.flushdb()