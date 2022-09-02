#!/bin/python3
"""
Microservices for data enrichment :
- /linkedinminer (JSON-LD schema.org format): full name and email -> fist name, last name, title, company, location, image, linkedin URL
- /whoiscompany : list of domains -> dict of domain : company name
- /emailvalidation : list of emails address -> dict of email address : validation status
- /...
- /socialprofiles : person (JSON-LD) -> list of social profiles
"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__copyright__ = "Ankaboot"
__license__ = "AGPL"

#fast api
from fastapi import FastAPI
from fastapi import Security, status
from fastapi.exceptions import HTTPException
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware

#typing & pydantic
from pydantic import BaseModel
from pydantic import EmailStr
from typing import List, Dict, Optional


#import other apis
from api import whoiscompany
from api import linkedin
from api.config import settings, log_config

#logging
import logging

#deal with fastapi issue with root/module loggers
#see https://github.com/tiangolo/uvicorn-gunicorn-fastapi-docker/issues/19
import logging.config
logging.config.dictConfig(log_config)
# create logger
log = logging.getLogger(__name__)

#others
import os
import secrets

#X-API-KEY protection
api_key_header_auth = APIKeyHeader(
    name=settings.api_key_name,
    description="Mandatory API Token, required for all endpoints",
    auto_error=True,
)

async def get_api_key(api_key_header: str = Security(api_key_header_auth)):
    if not any(secrets.compare_digest(api_key_header, api_key_v) for api_key_v in settings.api_keys):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )


#routing composition
from api import router
app = FastAPI(dependencies=[Security(get_api_key)])
#origins = ["http://localhost:"+os.environ.get("PORT", str(settings.server_port))]
app.add_middleware(
    CORSMiddleware,
#    allow_origins=origins,
    allow_credentials=True,
#    allow_methods=["*"],
#    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
   
    #TODO: fix issue related to child loggers levels in DEBUG mode
    uvicorn.run("main:app", port=int(os.environ.get("PORT", settings.server_port)), host="0.0.0.0", reload=True, debug=True)