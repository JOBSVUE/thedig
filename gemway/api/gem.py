"""Transmuter API"""


import requests

# config
from .config import settings

# fast api
from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status, Depends
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from fastapi_limiter.depends import WebSocketRateLimiter, RateLimiter

# websocket manager
from .websocketmanager import manager as ws_manager

# types
from typing import Annotated
from pydantic import EmailStr, HttpUrl, Field
from .person import Person, PersonRequest, PersonResponse
from .person import person_request_ta, person_response_ta, ValidationError

# logger
from loguru import logger as log

# json
import json

# service
from ..miners.linkedin import Bing, Brave, GoogleCustom, GoogleVertexAI, SearchChain
from ..miners.company import DomainName, Company, company_by_domain
from ..miners.domainlogo import guess_country, find_favicon
from ..miners.gravatar import gravatar as miner_gravatar
from ..miners.vision import SocialNetworkMiner
from ..miners.railway import Railway, JSONorNoneResponse
from ..miners.splitfullname import split_fullname
from ..miners.bio import find_jobtitle

# init fast api
router = APIRouter()

MAX_REQUESTS_PER_SEC = {"times": 3, "seconds": 10}
MAX_BULK = 1000

rw = Railway(router)


search_engines = SearchChain([
    GoogleCustom(token=settings.google_api_key, cx=settings.google_cx),
    Bing(customconfig=settings.bing_customconfig, token=settings.bing_api_key),
    Brave(token=settings.brave_api_key),
    GoogleVertexAI(
        service_account_info=json.loads(open(settings.google_credentials).read()),
        project_id=settings.google_vertexai_projectid,
        datastore_id=settings.google_vertexai_projectid
        )
])


@rw.register(field="email", update=("worksFor",))
async def worksfor(email: EmailStr) -> Person:
    # otherwise, the domain will give us the @org
    # except for public email providers
    domain = email.split("@")[1]
    works_for = {"worksFor": set()}
    if domain not in settings.public_email_providers:
        company = await company_by_domain(domain)
        if company:
            works_for['worksFor'].add(company["name"])
    return works_for


@rw.register(field="name")
async def linkedin(name: str, email: EmailStr = None, worksFor: str = None) -> Person:
    engine = search_engines.search(query=name, name=name)
    if not engine:
        return
    log.debug(engine.profiles)
    if type(worksFor) is set:
        worksFor = worksFor.copy().pop()
    engine.to_persons(worksFor=worksFor)
    return engine.persons[0] if engine.persons else None


@rw.register(field="email", update=("image",))
async def gravatar(email) -> Person:
    avatar = await miner_gravatar(email)
    return (
        {
            'image': {
                avatar,
            }
        }
        if avatar
        else {}
    )


@rw.register(field="image")
async def image(p: dict) -> Person:
    if "name" not in p:
        return

    snm = SocialNetworkMiner(p)
    await snm.image()

    snm.sameAs()

    if "OptOut" in snm.person:
        return {'OptOut': True}
    
    return snm.person


@rw.register(field="email")
async def social(p: dict) -> Person:
    if "name" not in p:
        return None
    snm = SocialNetworkMiner(p)

    # if there is an image, let's vision mine it
    # it will ads other social network URLs
    # if "image" in p:
    #    await snm.image()
    #    pass

    # fuzzy identifier miner
    # it's not an independent miner since identifier can't be mined
    # until confirmed social profiles are found
    await snm.identifier()

    snm.sameAs()

    if "OptOut" in snm.person:
        return {'OptOut': True}

    return snm.person


@rw.register(field="description", insert=("jobTitle",))
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


@rw.register(field="name", update=("givenName", "familyName"))
async def name(name: str, email: EmailStr) -> Person:
    splitted: Person = split_fullname(name, email.split("@")[1])
    return splitted


@rw.register(field="email", insert=("workLocation",))
async def country(email: EmailStr) -> Person:
    country = guess_country(email.split("@")[-1])
    return {"workLocation": country} if country else {}


@router.get(
    "/person/email/{email}", tags=("person", "railway"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))]
)
async def person_email(email: EmailStr, name: str) -> Person:
    rw_status, persond = await rw.person({"email": email, "name": name})
    if not rw_status:
        raise HTTPException(status_code=204)
    return persond


@router.post("/person/", tags=("person", "railway"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))])
async def person_post(person: Person) -> Person:
    rw_status, persond = await rw.person({"email": person['email'], "name": person['name']})
    if not rw_status:
        raise HTTPException(status_code=204)
    return persond


async def persons_bulk_background(
    persons: Annotated[Person, Field(max_items=MAX_BULK)],
    webhook_endpoint: HttpUrl
    ) -> bool:
    results = []
    for p in persons:
        success, enriched = await rw.person(**p)
        if success:
            results.append(enriched)
    try:
        r = requests.post(str(webhook_endpoint), json=results)
        r.raise_for_status()
    except requests.RequestException as e:
        log.error(e)


@router.post("/person/bulk", tags=("person", "railway"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))])
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

            rw_status = None

            rw_status, persond = await rw.person(person["person"])

            if rw_status:
                persond_count += 1

            response: PersonResponse = {"status": rw_status, "person": persond}
            person_response_ta.validate_python(response)

            # Send message when gemway finished
            await ws_manager.message(websocket, {person["uid"]: response})
    except WebSocketDisconnect:
        log.info(f"Websocket disconnected: {websocket}")
        ws_manager.disconnect(websocket)


@router.get("/company/domain/{domain}", tags=("company", "railway"), response_class=JSONorNoneResponse)
async def company_get(domain: Annotated[DomainName, Path(description="domain name")]) -> Company | None:
    """Search for public data on a company based on its domain

    Args:
        domain (DomainName)

    Returns:
        Company | None
    """
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

    return cmp
