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
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from pydantic import EmailStr
from typing import List, Dict, Optional


#import other apis
from api import whoiscompany
from api import linkedin
from api.config import Settings
settings = Settings()

#logging
import logging

#deal with fastapi issue with root/module loggers
import logging.config
#import yaml
#with open('logconfig.yml') as f:
#    config = yaml.load(f, Loader=yaml.FullLoader)
#    logging.config.dictConfig(config)
#create logger
log = logging.getLogger(__name__)

#others
import os

#routing composition
from api import router
app = FastAPI()
origins = ["http://localhost:"+os.environ.get("PORT", str(settings.server_port))]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#API key management
from fastapi_key_auth import AuthorizerMiddleware
app = FastAPI()
#hot patch to add ability to get the api keys from configuration instead of environment variables
def api_keys_in_env(self) -> List[Optional[str]]:
    api_keys = settings.api_keys
    return api_keys
AuthorizerMiddleware.api_keys_in_env = api_keys_in_env
app.add_middleware(AuthorizerMiddleware, public_paths=["/whoisdomain", "/linkedin", "/companylogo"])


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    #start server in debug mode
    uvicorn.run("main:app", port=int(os.environ.get("PORT", settings.server_port)), host="0.0.0.0", reload=True, debug=True)