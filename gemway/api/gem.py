"""Transmuter API"""

# config
from .config import settings

# fast api
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from fastapi_limiter.depends import WebSocketRateLimiter, RateLimiter

# websocket manager
from .websocketmanager import manager as ws_manager

# types
from pydantic import EmailStr, HttpUrl
from .person import Person, PersonRequest, PersonResponse
from .person import person_request_ta, person_response_ta, ValidationError

# logger
from loguru import logger as log

# json
import json

# service
from ..miners.linkedin import LinkedInSearch
from ..miners.company import Domain, Company, company_by_domain, company_from_whois
from ..miners.domainlogo import guess_country, find_favicon
from ..miners.gravatar import gravatar as miner_gravatar
from ..miners.vision import SocialNetworkMiner
from ..miners.railway import Railway, JSONorNoneResponse
from ..miners.splitfullname import split_fullname
from ..miners.bio import find_jobtitle

# init fast api
router = APIRouter()

search_api_params = {
    "google_api_key": settings.google_api_key,
    "google_cx": settings.google_cx,
    "query_type": settings.query_type,
}

MAX_REQUESTS_PER_SEC = {"times": 3, "seconds": 10}


rw = Railway(router)


@rw.register(field="name")
async def linkedin(name: str, email: EmailStr = None, worksFor: str = None) -> Person:
    miner = LinkedInSearch(search_api_params)
    person = await miner.search(
        name=name, email=email, company=worksFor
    )
    return person


@rw.register(
    field="url",
    update=(
        "worksFor",
        "jobTitle",
        "workLocation",
    ),
    insert=("givenName", "familyName"),
)
async def from_linkedin_url(name: str, url: HttpUrl) -> Person:
    person: Person = {}
    if "linkedin" in url:
        miner = LinkedInSearch(search_api_params)
        person.update(await miner.search(name=name, linkedin_url=url))
    return person


@rw.register(field="email", update=("image",))
async def gravatar(email) -> Person:
    avatar = await miner_gravatar(email)
    return (
        {'image': {avatar, }} if avatar
        else {}
    )


@rw.register(field="email")
async def social(p: dict) -> Person:
    if "name" not in p:
        return None
    snm = SocialNetworkMiner(p)

    # if there is an image, let's vision mine it
    # it will ads other social network URLs
    if "image" in p:
        await snm.image()
        pass

    # fuzzy identifier miner
    # it's not an independent miner since identifier can't be mined
    # until confirmed social profiles are found
    await snm.identifier()

    snm.sameAs()

    if "OptOut" in snm.person:
        return {'OptOut': True}

    return snm.person


#@rw.register(field="email", update=("worksFor",))
async def worksfor(email: EmailStr) -> Person:
    # otherwise, the domain will give us the @org
    # except for public email providers
    domain = email.split("@")[1]
    works_for = {}
    if domain not in settings.public_email_providers:
        company = company_from_whois(domain)
        if company:
            works_for['worksFor'] = company['name']
    return works_for


@rw.register(field="description", update=("jobTitle",))
async def bio(description: str = None) -> Person:
    desc: set[str] = {description, } if type(description) is str else description
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


@router.get("/person/email/{email}", tags=("person", "railway"), dependencies=[Depends(RateLimiter(**MAX_REQUESTS_PER_SEC))])
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
async def company_get(domain: Domain) -> Company | None:
    """Search for public data on a company based on its domain

    Args:
        domain (Domain)

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
            cmp['image'] = {favicon, }

    return cmp
