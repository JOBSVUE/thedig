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
def linkedin_bulk(persons: List[Person]):
    miner = LinkedInSearch(search_api_params, google=False, bing=True)
    return [miner.search(name=person.name, email=person.email) for person in persons]
