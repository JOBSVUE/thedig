"""LinkedIn Miner API"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__copyright__ = "Ankaboot"
__license__ = "AGPL"

#service
from miners.linkedinminer import LinkedInSearch

#fast api
from fastapi import APIRouter
from pydantic import BaseModel
from pydantic import EmailStr
from typing import List
from api.config import Settings

#init fast api
router = APIRouter()
settings = Settings()

#logging
#import logging

class Person(BaseModel):
    email: EmailStr
    name: str

search_api_params = {
    'google_api_key' : settings.google_api_key,
    'google_cx' : settings.google_cx,
    'bing_api_key' : settings.bing_api_key,
    'bing_customconfig' : settings.bing_customconfig
}

@router.get('/linkedin/{email}')
def linkedinminer_unique(email: EmailStr, name: str):
    miner = LinkedInSearch(search_api_params, google=True, bing=False)
    return miner.search(name=name, email=email)
    
@router.post('/linkedin')
def linkedinminer_bulk(persons: List[Person]):
    miner = LinkedInSearch(search_api_params, google=False, bing=True)
    return [miner.search(name=person.name, email=person.email) for person in persons]