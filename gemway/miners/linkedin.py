#!/bin/env python
"""
Mine public data from LinkedIn with an email address using Google Search API
Return format is JSON-LD simplified
"""

from abc import ABC, abstractmethod
from typing import Literal, Optional
import re
import time
import jwt

# needed for memory sharing between threads
from ..api.person import Person, dict_to_person
from pydantic import HttpUrl, BaseModel, model_validator, Field

# from curl_cffi import requests
import requests
from urllib.parse import quote

# log
from loguru import logger as log

# Fuzzy string match for person name identification
from rapidfuzz import fuzz

from .ISO3166 import ISO3166
from .utils import match_name

from html import unescape


HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "PATCH"]

# linkedin profile url with an ISO3166 country code regular expression
RE_LINKEDIN_URL = re.compile(
    r"^https?:\/\/((?P<countrycode>\w{2})|(:?www))\.linkedin\.com\/(?:public\-profile\/in|in|people)\/(?P<identifier>([%\w-]+))/?",
    re.U
)


def country_from_url(linkedin_url: str) -> str:
    """Country name based on the xx.linkedin.com profile url
    where xx is the ISO3166 country code else return None

    Args:
        linkedin_url (str): linkedin profile URL

    Returns:
        str: country name
    """
    match = RE_LINKEDIN_URL.match(linkedin_url)

    if match and match["countrycode"]:
        return ISO3166[match["countrycode"].upper()]


def parse_linkedin_title(title: str, name: str = None) -> dict:
    """parse LinkedIn Title that has this form
        Full Name - Title - Company | LinkedIn
        and sometimes (Google only):
        Full Name - Title - Company... | LinkedIn
        or even:
        Full Name - Company | LinkedIn
        Full Name - Title | LinkedIn
        it should always ends with '| LinkedIn'
    Args:
        title (str): title from LinkedIn page
    """
    if not title.endswith("LinkedIn") and not title.endswith("..."):
        raise ValueError("This is not a LinkedIn profile title")

    title_ = title.split(" | ")
    full_title = title_[0].split(" - ")
    if len(full_title) < 2:
        raise ValueError("This is not a LinkedIn profile title")

    if name and full_title[0].casefold() != name.casefold():
        raise ValueError("This may not its LinkedIn profile")

    result = {"name": full_title[0]}

    # when it's long, LinkedIn add a '...' suffix
    if len(full_title) == 3:
        secondpart = full_title[2].removesuffix("...").strip()
        firstpart = full_title[1].removesuffix("...").strip()
        # if last word got LinkedIn in it, it's not his company
        # except if this person does work for LinkedIn
        # this last case won't work
        if "LinkedIn" not in secondpart:
            result["jobTitle"] = firstpart
            result["worksFor"] = secondpart
        else:
            result["worksFor"] = firstpart

    return result


class LinkedInProfile(BaseModel):
    url: HttpUrl
    title: str
    name: str

    # not every search engine got them correctly
    description: Optional[str] = None
    image: Optional[HttpUrl] = None
    givenName: Optional[str] = None
    familyName: Optional[str] = None
    workLocation: Optional[str] = None

    # usually computed from the URL
    jobTitle: Optional[str] = None
    worksFor: Optional[str] = None
    country: Optional[str] = None
    identifier: Optional[str] = None

    # private attribute for regexp purposes
    match: Optional[dict] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def parse(self):
        self.match_url()
        self.parse_title()
        self.parse_url()

    def match_url(self):
        self.match = RE_LINKEDIN_URL.match(str(self.url))
        if not self.match:
            raise ValueError("Not a valid LinkedIn profile URL")

    def parse_url(self):
        if not self.country and self.match["countrycode"]:
            self.country = ISO3166[self.match["countrycode"].upper()]
        self.identifier = self.match["identifier"]

    def parse_title(self):
        r = parse_linkedin_title(self.title, self.name)
        if not r:
            raise ValueError("Not a valid LinkedIn Profile title")
        if not match_name(self.name, r['name'], fuzzy=False, condensed=False):
            raise ValueError("This LinkedIn profile name doesn't match")
        if "worksFor" in r:
            self.worksFor = r["worksFor"]
        if "jobTitle" in r:
            self.jobTitle = r["jobTitle"]

    
class Search(ABC):
    RICH_FIELDS = ['worksFor', 'jobTitle']
    RESULTS_COUNT = 10

    def __init__(
        self,
        endpoint: HttpUrl,
        method: HttpMethod,
        headers: dict = {},
        query_params: dict = {},
        body: dict = None
    ):
        self.endpoint = endpoint
        self.headers = headers
        self.query_params = query_params
        self.body = body
        self.method = method
        self.session = requests.Session()
        self.authenticate()

    @abstractmethod
    def search_query(self, query: str = None) -> dict:
        pass

    @abstractmethod
    def extract(self):
        pass
    
    @abstractmethod
    def authenticate(self):
        pass

    def raw_search(self, query: str):
        self.authenticate()
        search_q = self.search_query(query)
        if self.method == "GET":
            self.query_params.update(search_q)
        elif self.method == "POST":
            self.body.update(search_q)
        else:
            raise ValueError(f"Not a supported HTTP method: {self.method}")

        prepped_req = requests.Request(
            method=self.method,
            url=self.endpoint,
            params=self.query_params,
            headers=self.headers,
            json=self.body
        ).prepare()
            
        r = self.session.send(prepped_req)
        r.raise_for_status()

        self.raw_results = r.json()

    def search(self, query: str, name: str):
        self.raw_search(query)
        self.extract()
        
        # returns the first or the most complete
        self.profiles = []
        for r in self.results:
            try:
                self.profiles.append(LinkedInProfile(**r, **{"name": name}))
                #if all(getattr(profiles[-1], field) for field in self.RICH_FIELDS):
                #    return profiles[-1]
            except ValueError as e:
                log.debug(f"Not a valid {name} {r} LinkedInprofile: {e}")

        return self.profiles

    def persons(self):
        self.persons = []
        for profile in self.profiles:
            self.persons.append(dict_to_person(dict(
                name=profile.name,
                url=profile.url,
                sameAs={profile.url},
                description=profile.description,
                workLocation={profile.workLocation or profile.country},
                givenName=profile.givenName,
                familyName=profile.familyName,
                identifier={profile.identifier},
                image=profile.image,
                jobTitle=profile.jobTitle,
                worksFor=profile.worksFor
            ), unsetvoid=True))


class GoogleVertexAI(Search):
    TOKEN_URI = "https://oauth2.googleapis.com/token"
    TOKEN_LIFEDURATION = 3600
    SCOPE = "https://www.googleapis.com/auth/cloud-platform"    
    ENDPOINT = "https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/{region}/collections/default_collection/engines/{datastore_id}/servingConfigs/default_search:search"

    def __init__(
        self,
        service_account_info: dict,
        project_id: str,
        datastore_id: str,
        region: str = "global",
    ):
        self.service_account_info = service_account_info
        self.access_token = None
        self.token_expiry = 0  # Timestamp when the token will expire

        super().__init__(
                endpoint=self.ENDPOINT.format(
                    project_id=project_id,
                    region=region,
                    datastore_id=datastore_id
                    ),
                method="POST",
                body={
                    "pageSize": self.RESULTS_COUNT,
                    "contentSearchSpec": {"snippetSpec": {"returnSnippet": False}}
                },
                headers={
                    "Content-Type": "application/json",
                }
            )

    def authenticate(self):
        # Check if the token is still valid and not about to expire
        if self.access_token and time.time() < self.token_expiry - 60 * 5:
            return
        
        # Generate a JWT for the service account
        now = int(time.time())
        payload = {
            "iss": self.service_account_info["client_email"],
            "sub": self.service_account_info["client_email"],
            "aud": self.TOKEN_URI,
            "iat": now,
            "exp": now + 3600,  # Token valid for 1 hour
            "scope": self.SCOPE,
        }

        # Sign the JWT with the service account's private key
        signed_jwt = jwt.encode(payload, self.service_account_info["private_key"], algorithm="RS256")

        # Request an access token
        token_response = requests.post(self.TOKEN_URI, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
        })

        token_response.raise_for_status()
        token_json = token_response.json()
        self.access_token = token_json["access_token"]
        self.token_expiry = now + token_json.get("expires_in", self.TOKEN_LIFEDURATION)

        # Update headers with the new access token
        self.headers["Authorization"] = f"Bearer {self.access_token}"
   
    def raw_search(self, name: str):
        self.authenticate()
        return super().raw_search(name)

    def search_query(self, query: str) -> dict:
        return {**self.body, "query": query}

    def extract(self):
        self.results = [
            {
                "title": p.get('og:title'),
                "url": p.get('og:url'),
                "description": unescape(p.get('og:description')).replace("<br>", "\n"),
                "givenName": p.get('profile:first_name'),
                "familyName": p.get('profile:last_name'),
                "image": p.get('og:image'),
                "country": ISO3166.get(p.get('locale').split('_')[-1]),
                }
            for p in map(
                lambda r: r.get('document', {}).get('derivedStructData', {}).get('pagemap', {}).get('metatags', [{}])[0],
                self.raw_results.get("results", [])
            )
        ]


class Brave(Search):
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
    HEADERS = {
        "X-Subscription-Token": None,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    QUERY_PARAMS = {
        "resultfilter": "web",
        #"goggles_id": "https://raw.githubusercontent.com/carlopezzuto/google-linkedin/main/googgleLI",
        "count": Search.RESULTS_COUNT,
        "country": "us",
        "search_lang": "en",
    }

    def __init__(
        self,
        token: str,
    ):
        self.token = token
        super().__init__(
                endpoint=self.ENDPOINT,
                method="GET",
                headers=self.HEADERS,
                query_params=self.QUERY_PARAMS
        )
        
    def authenticate(self):
        self.headers['X-Subscription-Token'] = self.token

    def search_query(self, query: str):
        return {"q": f"site:linkedin.com/in {query}"}

    def extract(self):
        self.results = [
            {"title": p['title'], "url": p['url'], "description": p['description']}
            for p in self.raw_results.get("web", {}).get("results", {}) if p
        ]


class Bing(Search):
    ENDPOINT = "https://api.bing.microsoft.com/v7.0/custom/search"
    QUERY_PARAMS = {
        "count": Search.RESULTS_COUNT,
    }

    def __init__(
        self,
        token: str,
        customconfig: str,
    ):
        self.token = token
        super().__init__(
                endpoint=self.ENDPOINT,
                method="GET",
                query_params=self.QUERY_PARAMS,
        )
        self.query_params["customconfig"] = customconfig

    def authenticate(self):
        self.headers['Ocp-Apim-Subscription-Key'] = self.token

    def search_query(self, query: str) -> dict:
        return {"q": query}

    def extract(self):
        self.results = []
        if (
            "webPages" not in self.raw_results
            or not self.raw_results["webPages"].get("value")
        ):
            return   

        for result in self.raw_results["webPages"]["value"]:
            self.results.append({
                "title": result["name"],
                "description": result["snippet"],
                "url": result["url"],
                "image": result.get('openGraphImage', {}).get("contentUrl"),
            })

            # Bing also gives you sometimes location
            for item in result.get("richFacts", ()):
                if item['hint']['text'] != "ADDRESS:LOCATIONGENERAL":
                    continue
                address = item["items"][0]["text"].split(", ")
                # however sometimes the address isn't correctly identified by Bing
                if len(address) >= 3:
                    self.results[-1]["workLocation"] = ", ".join(address)


class GoogleCustom(Search):
    ENDPOINT = "https://www.googleapis.com/customsearch/v1/siterestrict"
    QUERY_PARAMS = {
        "fields": "items(title,link,pagemap/cse_thumbnail,pagemap/metatags/profile:first_name,pagemap/metatags/profile:last_name,pagemap/metatags/og:image,pagemap/metatags/og:description)",
        "num": Search.RESULTS_COUNT,
        "query_type": 'q',
    }

    def __init__(
        self,
        token: str,
        cx: str,
    ):
        self.token = token
        self.cx = cx
        super().__init__(
                endpoint=self.ENDPOINT,
                method="GET",
                query_params=self.QUERY_PARAMS
        )
        
    def authenticate(self):
        self.headers.update({
            "key": self.token,
            "cx": self.cx,
        })

    def search_query(self, query: str):
        return {"q": query}

    def extract(self):
        self.results = []

        if not self.raw_results.get("items"):
            return

        self.results = [
            {
                "givenName": r["pagemap"]["metatags"][0]["profile:first_name"],
                "familyName": r["pagemap"]["metatags"][0]["profile:last_name"],
                "description": r["pagemap"]["metatags"][0]["og:description"],
                "url": r["link"],
                "image": r["pagemap"]["metatags"][0]["og:image"]
            }
            for r in self.raw_results["items"] if r.get("pagemap", {}).get("metatags", {})
        ]
