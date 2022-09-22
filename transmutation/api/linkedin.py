"""LinkedIn Miner API"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__copyright__ = "Ankaboot"
__license__ = "AGPL"


import requests
import time

# config
from .config import settings
from .config import log

# fast api
from fastapi import APIRouter
from fastapi import Header
from fastapi import BackgroundTasks

# types
from pydantic import EmailStr
from pydantic import SecretStr
from typing import List

# Schema.org Person
from pydantic_schemaorg.Person import Person

# service
from ..miners.linkedin import LinkedInSearch

# celery tasks
from .tasks import task
from .tasks import AsyncResult

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
async def linkedin_unique(email: EmailStr, name: str) -> Person:
    """LinkedIn - enrich only one person identified by his name and email

    Args:
        email (EmailStr): email address
        name (str): full name

    Returns:
        Person: Person Schema.org
    """
    miner = LinkedInSearch(search_api_params, google=True, bing=False)
    person = miner.search(name=name, email=email)
    return person

@router.post(
    "/linkedin",
    response_model=List[Person],
    response_model_exclude_none=True
    )    
async def linkedin_bulk(
    persons: list[Person],
    ) -> List[Person]:
    """LinkedIn - enrich several persons and returns them

    Args:
        persons (list[Person]): list of Persons
    Returns:
        list[Person]: list of Persons
    """
    # remove persons with no name
    persons = list(filter(lambda p: p.name, persons))

    miner = LinkedInSearch(bulk=True, search_api_params=search_api_params)

    return miner.bulk(persons)

@task
def patch_person(name, email, search_api_params: dict, callback_params: dict):
    miner = LinkedInSearch(search_api_params=search_api_params)
    try:
        p_patched = miner.search(name=name, email=email)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            log.info("Search API Rate limits hit. We pause then try again in 1 minute.")
            # Google limits 100 requests / minute
            time.sleep(60)
            p_patched = miner.search(name=p.name, email=p.email)
        else:
            log.error(e)

    if not p_patched:
        return None
    
    # for SQL link between tables,
    # we need to set worksFor to the Organization primary key
    if p_patched.worksFor:
        w_json = p_patched.worksFor.json(exclude={'type_'})
        p_patched.worksFor = p_patched.worksFor.name
        r = requests.post(f"{endpoint}organizations", data=w_json, headers=headers)
    
    p_json = p_patched.json(exclude={'type_'})
    r = requests.post(f"{endpoint}persons", data=p_json, headers=headers)   

    return r.ok

@task
def patch_personDB(endpoint: str, headers: dict, persons: List[dict]) -> int:
    i = 0
    miner = LinkedInSearch(bulk=True, search_api_params=search_api_params)
    for p in persons:
        try:
            p_patched = miner.search(name=p['name'], email=p['email'])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                log.info("Search API Rate limits hit. We pause then try again in 1 minute.")
                # Google limits 100 requests / minute
                time.sleep(60)
                p_patched = miner.search(name=p.name, email=p.email)
            else:
                log.error(e)

        if not p_patched:
            continue
        
        # for SQL link between tables,
        # we need to set worksFor to the Organization primary key
        if p_patched.worksFor:
            w_json = p_patched.worksFor.json(exclude={'type_'})
            p_patched.worksFor = p_patched.worksFor.name
            r = requests.post(f"{endpoint}organizations", data=w_json, headers=headers)
        
        p_json = p_patched.json(exclude={'type_'})
        r = requests.post(f"{endpoint}persons", data=p_json, headers=headers)   
        
        # useless counter but who knows?
        i += 1 if r.ok else 0

@router.patch(
    "/linkedin",
    )    
async def linkedin_callback(
    persons: list[Person],
#    background: BackgroundTasks,
    x_callback_endpoint: str = Header(),
    x_callback_secret: SecretStr = Header(),
    )-> str:

    # remove persons with no name
    # persons = list(filter(lambda p: p.name, persons))
    persons = [p.dict(exclude_unset=True) for p in persons if p.name]
    
    callback_secret = x_callback_secret.get_secret_value()
    callback_headers = {
        "apikey" : callback_secret,
        "Authorization" : f"Bearer {callback_secret}",
        "Prefer": "resolution=merge-duplicates",
        "Content-type" : "application/json"
    }
    callback_params = {"endpoint" : x_callback_endpoint, "headers" : callback_headers}

    #background.add_task(patch_personDB, x_callback_endpoint, callback_headers, persons)
    miner = LinkedInSearch(bulk=True, search_api_params=search_api_params)
    
    # t = patch_person.delay(persons[0].name, persons[0].email, search_api_params, callback_params)
    t = patch_personDB.delay(x_callback_endpoint, callback_headers, persons)
    return t.id

@router.get(
    "/tasks/{task_id}"
)
def linkedin_task(task_id: str):
    task_result = AsyncResult(task_id)
    
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    }
    return result