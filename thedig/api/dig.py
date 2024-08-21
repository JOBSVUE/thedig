"""Transmuter API"""


# json
import json

# types
from typing import Annotated

import asyncio
import requests
from hashlib import sha256

# fast api
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from fastapi_limiter.depends import RateLimiter, WebSocketRateLimiter

# logger
from loguru import logger as log
from pydantic import EmailStr, Field, HttpUrl

from ..excavators.archaeology import Archeologist, JSONorNoneResponse, json_dumps
from ..excavators.bio import find_jobtitle
from ..excavators.company import Company, DomainName, company_by_domain
from ..excavators.domainlogo import find_favicon, guess_country
from ..excavators.gravatar import gravatar

# service
from ..excavators.linkedin import Bing, Brave, GoogleCustom, GoogleVertexAI, SearchChain
from ..excavators.splitfullname import split_fullname
from ..excavators.vision import SocialNetworkMiner
from ..excavators.utils import match_name

# config
from .config import settings, Settings, setup_cache
from .person import (
    Person,
    PersonRequest,
    PersonResponse,
    ValidationError,
    person_request_ta,
    person_response_ta,
)

# websocket manager
from .websocketmanager import manager as ws_manager

MAX_REQUESTS_PER_SEC = {"times": 3, "seconds": 10}
MAX_BULK = 1000

# init fast api
router = APIRouter()
ar = Archeologist(router)

@ar.register(field="email", update=("worksFor",))
async def worksfor(email: EmailStr) -> Person:
    # except for public email providers
    domain = email.split("@")[1]
    works_for = {"worksFor": set()}
    if domain not in settings.public_email_providers:
        company = await company_by_domain(domain)
        if company:
            works_for['worksFor'].add(company["name"])
    return works_for


@ar.register(field="name")
async def linkedin(name: str, email: EmailStr = None, worksFor: str = None) -> Person:
    engine = SearchChain(settings).search(query=name, name=name)
    if not engine:
        return
    log.debug(engine.profiles)
    if type(worksFor) is set:
        worksFor = worksFor.copy().pop()
    engine.to_persons(worksFor=worksFor)
    return engine.persons[0] if engine.persons else None


@ar.register(field="email", update=("image",))
async def exc_gravatar(email) -> Person:
    avatar = await gravatar(email)
    return (
        {
            'image': {
                avatar,
            }
        }
        if avatar
        else {}
    )


@ar.register(field="image")
async def image(p: dict) -> Person:
    if "name" not in p:
        return

    snm = SocialNetworkMiner(p)
    await snm.image()

    snm.sameAs()

    if "OptOut" in snm.person:
        return {'OptOut': True}

    return snm.person


@ar.register(field="email")
async def social(p: dict) -> Person:
    if "name" not in p:
        return None
    snm = SocialNetworkMiner(p)

    # fuzzy identifier miner
    # it's not an independent miner since identifier can't be mined
    # until confirmed social profiles are found
    await snm.identifier()

    snm.sameAs()

    if "OptOut" in snm.person:
        return {'OptOut': True}

    return snm.person


@ar.register(field="description", insert=("jobTitle",))
async def bio(description: str = None) -> Person:
    desc: set[str] = (
        {
            description,
        }
        if type(description) is str
        else description
    )
    job_title = {}
    jt = set()
    for d in desc:
        jobtitle = find_jobtitle(d)
        if jobtitle:
            jt |= jobtitle

    if jt:
        job_title['jobTitle'] = jt

    return job_title


@ar.register(field="name", update=("givenName", "familyName"))
async def name(name: str, email: EmailStr) -> Person:
    splitted: Person = split_fullname(name, email.split("@")[1])
    return splitted


@ar.register(field="email", insert=("workLocation",))
async def country(email: EmailStr) -> Person:
    country = guess_country(email.split("@")[-1])
    return {"workLocation": country} if country else {}


@router.get(
    "/person/email/{email}", tags=("person", "archaeology"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))]
)
async def person_email(email: EmailStr, name: str) -> Person:
    ar_status, persond = await ar.person({"email": email, "name": name})
    if not ar_status:
        raise HTTPException(status_code=204)
    return persond


@router.post("/person/", tags=("person", "archaeology"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))])
async def person_post(person: Person) -> Person:
    ar_status, persond = await ar.person({"email": person['email'], "name": person['name']})
    if not ar_status:
        raise HTTPException(status_code=204)
    return persond


async def persons_bulk_background(
    persons: Annotated[Person, Field(max_items=MAX_BULK)],
    webhook_endpoint: HttpUrl
    ) -> bool:
    results = []
    for p in persons:
        success, enriched = await ar.person(p)
        if success:
            results.append(enriched)
    try:
        r = requests.post(str(webhook_endpoint), json=json_dumps(results))
        r.raise_for_status()
        log.debug(f"Endpoint answered: {r.json()}")
    except requests.RequestException as e:
        log.error(e)


@router.post("/person/bulk", tags=("person", "archaeology"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))])
async def persons_bulk(persons: list[Person], endpoint: HttpUrl, background: BackgroundTasks) -> bool:
    background.add_task(persons_bulk_background, persons, endpoint)
    return True


@router.websocket("/person/{user_id}/websocket")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await ws_manager.connect(websocket)
    ratelimit = WebSocketRateLimiter(**MAX_REQUESTS_PER_SEC)
    persond_count = 0
    log.info(f"Websocket connected: {websocket} - {user_id}")

    try:
        while True:
            # Wait for any message from the client
            await ratelimit(websocket)

            try:
                person: PersonRequest = await websocket.receive_json()
                person_request_ta.validate_python(person)
            except json.JSONDecodeError as e:
                log.debug(f"JSON malformed: {e}")
                raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)
            except ValidationError:
                log.debug(f"invalid data: {person}")
                raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)

            ar_status = None

            ar_status, persond = await ar.person(person["person"])

            if ar_status:
                persond_count += 1

            response: PersonResponse = {"status": ar_status, "person": persond}
            person_response_ta.validate_python(response)

            # Send message when thedig finished
            await ws_manager.message(websocket, {person["uid"]: response})
    except WebSocketDisconnect:
        log.info(f"Websocket disconnected: {websocket}")
        ws_manager.disconnect(websocket)


@router.post("/person/optout", tags=("person", "GDPR"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))])
async def person_optout(person: Person) -> bool:
    """Opt-out person from thedig to prevent future archeology requests and GDPR compliance

    Args:
        person (Person): person to opt-out

    Returns:
        bool: success
    """
    if not ar.cache:
        raise HTTPException(status_code=503, detail="Cache is not available")
    p_c = await ar.cache.get(
        sha256(person["email"].encode("utf-8")).hexdigest()
        )
    if p_c:
        p = json.loads(p_c)
        if p["OptOut"]:
            return True
        elif match_name(person["name"], p["name"], fuzzy=False):
            await ar.cache.delete(
                sha256(person["email"].encode("utf-8")).hexdigest()
                )
        else:
            return HTTPException(status_code=400, detail="Name does not match")

    # hash to avoid storing personal data
    person = {
        "name": sha256(person["name"].encode("utf-8")).hexdigest(),
        "email": "donotdigme@yopmail.com",
        "OptOut": True
    }
    await ar.cache.set(
        sha256(person["email"].encode("utf-8")).hexdigest(),
        json_dumps(person)
        )
    return True


@router.get("/company/domain/{domain}", tags=("company", "archaeology"), response_class=JSONorNoneResponse)
async def company_get(domain: Annotated[DomainName, Path(description="domain name")]) -> Company | None:
    """Search for public data on a company based on its domain

    Args:
        domain (DomainName)

    Returns:
        Company | None
    """
    if await cache_company.get(domain):
        return json.loads(await cache_company.get(domain))

    cmp = await company_by_domain(domain)
    if not cmp or 'name' not in cmp:
        return None
    favicon = find_favicon(domain)
    if favicon:
        if 'logo' not in cmp:
            cmp['logo'] = favicon
        if 'image' in cmp:
            cmp['image'].add(favicon)
        else:
            cmp['image'] = {
                favicon,
            }

    await cache_company.set(
        domain,
        json_dumps(cmp),
        ex=settings.cache_expiration_company
        )

    return cmp