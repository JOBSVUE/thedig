"""
Various utilities
"""

from rapidfuzz import fuzz
from fake_useragent import UserAgent
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


def match_name(name: str, text: str) -> bool:
    if not name:
        return True
    return fuzz.partial_token_sort_ratio(name, text) >= TOKEN_RATIO


def normalize(name: str, whitespace: str="") -> str:
    return name.encode("ASCII", "ignore").strip().lower().decode().replace(" ", whitespace)
