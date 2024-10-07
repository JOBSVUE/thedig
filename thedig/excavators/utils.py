"""
Various utilities
"""

from pydantic import HttpUrl
from rapidfuzz import fuzz
from fake_useragent import UserAgent
import urllib
from .ISO3166 import ISO3166

TOKEN_RATIO = 82

COUNTRY_TLD_EXCLUSION = {
    "ai",
    "am",
    "at",
    "bz",
    "cc",
    "co",
    "fi",
    "fm",
    "im",
    "in",
    "io",
    "is",
    "it",
    "ly",
    "me",
    "mu",
    "nu",
    "re",
    "sk",
    "sh",
    "tk",
    "to",
    "tv",
    "ws",
}


def absolutize(url: str, base_url: HttpUrl) -> HttpUrl:
    if str(url).startswith("http"):
        absolute_url = url
    else:
        absolute_url = urllib.parse.urljoin(base_url, str(url))
    # if this didn't work, return empty string
    if not str(absolute_url).startswith("http"):
        absolute_url = ""
    return absolute_url


def get_tld(domain: str) -> str:
    return domain.split(".")[-1]


def guess_country(domain: str) -> str:
    tld = get_tld(domain)
    # tld used generically are irrelevant to guess country
    if tld in COUNTRY_TLD_EXCLUSION:
        return None
    return ISO3166.get(tld.upper())


def domain_to_urls(domain: str) -> list[str]:
    """Build hypothetical websites URL from a domain
    Gives priority to https then to www

    Args:
        domain (str): domain name

    Returns:
        list of urls
    """
    return [
        f"https://www.{domain}",
        f"https://{domain}",
        #    f"http://www.{domain}",
        #    f"http://{domain}",
    ]


def ua_headers(random: bool = False) -> dict:
    """
    generate a random user-agent
    basic techniques against bot blockers
    """
    ua = UserAgent()
    if random:
        user_agent = ua.random
    else:
        user_agent = ua.chrome
    return {"user-agent": user_agent}


def match_name(name: str,
               text: str,
               fuzzy: bool = True,
               acronym: bool = False,
               condensed: bool = True) -> bool:
    if not name:
        return True

    if fuzzy and fuzz.partial_token_sort_ratio(name, text) >= TOKEN_RATIO:
        return True

    if condensed:
        text = text.replace(' ', '')

    match = (name.casefold() == text.casefold())

    if not match and acronym:
        match = (name.casefold() == filter(str.isupper, text))

    return match


def normalize(name: str, replace: dict = {' ': ''}) -> str:
    name = str(name.encode("ASCII", "ignore").strip().decode()).casefold()
    for k, v in replace.items():
        name = name.replace(k, v)
    return name
