#!/bin/python3
"""
Return company name based on domain's email address whois
"""
import logging
from datetime import date
from typing import Required
from typing_extensions import TypedDict
from pydantic import EmailStr, HttpUrl
import whoisdomain as whois


TO_IGNORE = {
    "Statutory Masking Enabled",
    "Privacy service provided by Withheld for Privacy ehf",
    "Data Protected",
    "Whois Privacy Service",
    "Redacted for Privacy Purposes",
    "REDACTED FOR PRIVACY",
}

COMPANY_TYPE_ABBR = {
    'Co',
    'Corp',
    'EURL',
    'Inc',
    'LLC',
    'Ltd',
    'SA',
    'SARL',
    'SAS',
    'SASU',
}


log = logging.getLogger(__name__)


class Organization(TypedDict, total=False):
    name: Required[str]
    founder: set[str]
    logo: set[HttpUrl]
    legalName: str
    location: set[str]
    numberOfEmployees: str #often a range
    image: set[HttpUrl]
    sameAs: set[HttpUrl]
    url: HttpUrl
    email: EmailStr
    telephone: str
    foundingDate: date
    

def get_domain(email: str) -> str:
    return email.split("@")[1]


def remove_company_type_abbrv(company: str) -> str:
    last_word = company.split(', ')[-1].split(' ')[-1].removesuffix('.')
    if last_word in COMPANY_TYPE_ABBR:
        return (
            company
            .removesuffix('.')
            .removesuffix(last_word)
            .removesuffix(", ")
            .strip()
            )


def get_company(domain: str) -> Organization | None:
    try:
        result = whois.query(domain, ignore_returncode=True)
    except whois.WhoisPrivateRegistry as e:
        log.error(f"Whois failed: {e}")
        return None
    except whois.WhoisCommandFailed as e:
        log.error(f"Whois failed: {e}")
        return None

    if not result:
        return None

    # the company name is the registrant in *this* whois implementation
    company = result.registrant

    if not company:
        return None
        
    # there is some domains who hide their real registrant name
    if company in TO_IGNORE:
        log.debug(f"Registrant in ignore list: {company}")
        return None

    org: Organization = Organization(name=remove_company_type_abbrv(company), legalName=company)
    
    return org


def get_company_from_email(email: str) -> Organization:
    """return company name from an email address

    Args:
        email (str): email address

    Returns:
        str: company name
    """
    domain = get_domain(email)
    return get_company(domain)
