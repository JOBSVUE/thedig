"""LinkedIn Miner API"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__copyright__ = "Ankaboot"
__license__ = "AGPL"

# fast api
from fastapi import APIRouter
from pydantic import BaseModel
from pydantic import EmailStr
from typing import List
from .config import settings
from .config import log

# Schema.org Person
from pydantic_schemaorg.Person import Person

# service
from ..miners.linkedin import LinkedInSearch

# init fast api
router = APIRouter()

search_api_params = {
    "google_api_key": settings.google_api_key,
    "google_cx": settings.google_cx,
    "bing_api_key": settings.bing_api_key,
    "bing_customconfig": settings.bing_customconfig,
}

@router.get(
    "/linkedin/{email}",
    response_model=Person,
    response_model_exclude_unset=True
    )
def linkedin_unique(email: EmailStr, name: str):
    miner = LinkedInSearch(search_api_params, google=True, bing=False)
    return miner.search(name=name, email=email)


@router.post(
    "/linkedin",
    response_model=List[Person],
    response_model_exclude_none=True
    )    
def linkedin_bulk(persons: list[Person]) -> list[Person]:
    miner = LinkedInSearch(bulk=True, search_api_params=search_api_params)
    r = []

    # remove persons with no name
    persons = list(filter(lambda person: person.name, persons))

    randomize = True
    batch = 10

    if randomize:
        import random
        random.shuffle(persons)
    
    r = miner.bulk(persons[:min(batch,len(persons))-1])    
    return r
