#!/bin/python3
"""
Grab informations about a company from its domain
"""
import json
import logging
from typing import Required
from typing_extensions import TypedDict
import urllib.parse
from pydantic import EmailStr, HttpUrl
import hrequests
import pydantic
import whoisdomain as whois
from .utils import normalize
import random

QUERY_TIMEOUT = 10

TO_IGNORE = (
    "<data not disclosed>",
    "Contact Privacy Inc. Customer",
    "Data Protected",
    "Domain Privacy Trustee SA",
    "Domains By Proxy, LLC",
    'Data Privacy Protected',
    'Domain Privacy Service FBO Registrant',
    'Domain Privacy Service FBO Registrant.',
    'Domain Privacy Trustee',
    "Domain Protection Services",
    "hidden",
    "Identity Protect Limited",
    "Identity Protection Service",
    'Jewella Privacy LLC Privacy ID#',
    'MyPrivacy.net',
    "NameBrightPrivacy.com",
    "NO FORMAT!",
    "None",
    "Not Disclosed",
    "Not shown, please visit www.dnsbelgium.be for webbased whois.",
    "[PRIVATE]",
    'Privacy Protection',
    'PrivacyGuardian.org llc',
    "Privacy service provided by Withheld for Privacy ehf",
    "REDACTED FOR PRIVACY",
    'Redacted for GDPR privacy',
    "Redacted for Privacy",
    "Redacted for Privacy Purposes",
    "Statutory Masking Enabled",
    'See PrivacyGuardian.org',
    'Super domains privacy',
    'Whois Privacy',
    'Whois Privacy Protection Foundation',
    'Whois Privacy Protection Service',
    'Whois Privacy Protection Service by VALUE-DOMAIN',
    'Whois Privacy Protection Service by onamae.com',
    "Whois Privacy Service",
    "Whoisprotection.cc",
    "Withheld for Privacy Purposes",
)

COMPANY_TYPE_ABBR = {
    'Co',
    'Corp',
    'Corporation',
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

Domain = pydantic.constr(
    pattern=r"^([\w-]+\.)*(\w[\w-]{0,66})\.(?P<tld>[a-z]{2,18})$",
    strict=True
    )

HTTP_PROXY = {
    'http': "http://127.0.0.1:41255",
    'https': "http://127.0.0.1:41255",
#    'http': "socks5://mail.leadminer.io:8060",
#    'https': "socks5://mail.leadminer.io:8060",
    }


class Company(TypedDict, total=False):
    name: Required[str]
    description: set[str]
    address: set[str]
    description: set[str]
    founder: set[str]
    logo: HttpUrl
    image: set[HttpUrl]
    industry: set[str]
    legalName: str
    location: set[str]
    # often a range x-y
    numberOfEmployees: str
    image: set[HttpUrl]
    sameAs: set[HttpUrl]
    url: HttpUrl
    email: EmailStr
    telephone: str
    foundingDate: str
    # not native to Organization schema.org
    # unstructured
    revenue: str


def get_domain(email: EmailStr) -> str:
    return email.split("@")[1]


def get_name(domain: Domain) -> str | None:
    d = domain.split(".")
    if len(d) > 2:
        return None
    return d[-2].replace('-', ' ').lower()


def remove_shorter_duplicates(data: set):
    for d in data.copy():
        # it has been removed, so continue
        if d not in data:
            continue
        data_c = data.copy() - {d, }
        for d_c in data_c:
            if d_c in d:
                data.remove(d_c)
    return data


def remove_company_type_abbrv(company: str) -> str:
    last_word = company.split(', ')[-1].split(' ')[-1].removesuffix('.')
    if last_word in COMPANY_TYPE_ABBR:
        company = (
            company
            .removesuffix('.')
            .removesuffix(last_word)
            .removesuffix(", ")
            .strip()
            )
    return company


def company_from_whois(domain: Domain) -> Company | None:
    try:
        result = whois.query(domain, ignore_returncode=True)
    except whois.WhoisPrivateRegistry as e:
        log.error(f"Whois failed: {e}")
        return None
    except whois.WhoisCommandFailed as e:
        log.error(f"Whois failed: {e}")
        return None
    except whois.FailedParsingWhoisOutput as e:
        log.error(f"Whois failed: {e}")
        return None
    except whois.UnknownTld as e:
        log.error(f"Whois failed: {e}")
        return None       

    if not result:
        return None

    # the company name is the registrant in *this* whois implementation
    company = result.registrant

    if not company or company == result.registrar:
        log.debug("No result or the registrar is the registrant")
        return None

    # there is some domains who hide their real registrant name
    if any(ignore in company for ignore in TO_IGNORE):
        log.debug(f"Registrant in ignore list: {company}")
        return None

    cmp: Company = Company(name=remove_company_type_abbrv(company), legalName=company)

    return cmp


async def company_by_domain(domain: Domain) -> Company | None:
    """Will get company using its name

    Args:
        domain (str): domain of the company

    Returns:
        Company: company object
    """
    cmp: Company = company_from_whois(domain) or {}
    if not cmp:
        return cmp

    # to be efficient web scrapping should gave no false positive
    # domain MUST BE [name of the company in whois].tld
    probable_name = get_name(domain)
    if not probable_name or probable_name not in cmp['name'].lower():
        return cmp

    web_cmp: Company = await company_from_web(domain)
    if web_cmp:
        for field, value in web_cmp.items():
            if type(value) is set and len(value) > 1:
                cmp[field] = remove_shorter_duplicates(value)
            else:
                cmp[field] = value

    return cmp


async def company_from_web(domain: Domain) -> Company | None:
    name = get_name(domain)
    if not name:
        return None
    company = {}
    cmps = []
    cmps.extend((
        await company_from_crunchbase(name, domain),
        await company_from_indeed(name, domain),
        await company_from_linkedin(name, domain),
    ))
    if domain[-3:] == ".fr":
        cmps.append(await company_from_societecom(name))
    for cmp in cmps:
        if not cmp or all(name not in sameAs for sameAs in cmp.get('sameAs', [])):
            continue
        for k, v in cmp.items():
            if type(v) is set and k in company:
                company[k].update(v)
            else:
                company[k] = v
    return company


async def find_company_societecom(name: str) -> HttpUrl | None:
    r = hrequests.get(
        f"https://www.societe.com/cgi-bin/liste?ori=avance&nom={urllib.parse.quote(name)}&exa=on",
        timeout=QUERY_TIMEOUT
        )
    if not r.ok:
        log.error(f"Couldn't get results for {r.url}: {r.status_code} : {r.reason}")
        return None

    links = r.html.find_all("a.ResultBloc__link__content")
    if not links:
        log.warning(f"No results for that name: {name}")
        return None
    # there is at least 6 links when only one result
    if len(links) > 6:
        log.warning(f"More than one company found with that name: {name}")
        return None

    return f"https://www.societe.com{links[0].attrs['href']}"


async def company_from_societecom(name: str) -> Company | None:
    url = await find_company_societecom(name)

    if not url:
        return None

    r = hrequests.get(url, timeout=QUERY_TIMEOUT)
    if not r.ok:
        log.error(f"{r.url} : {r.reason}")
        return None

    cmp: Company = Company(
        name=name,
        foundingDate=r.html.find("span.TableTextGenerique").text,
        sameAs={url, },
    )

    # eg "1 à 3 salariés"
    number_of_employees = r.html.find("div#trancheeff-histo-description") or r.html.find("#effmoy-histo-description")
    if number_of_employees:
        number_of_employees = number_of_employees.text.split()
        if len(number_of_employees) > 1:
            cmp['numberOfEmployees'] = f"{number_of_employees[0]}-{number_of_employees[2]}"
        else:
            cmp['numberOfEmployees'] = number_of_employees[0]

    address = r.html.find("div.CompanyIdentity__adress__around").text.splitlines()
    cmp['address'] = {", ".join(address), }
    cmp['location'] = {", ".join(address[-2:])[6:], }

    return cmp


async def company_from_indeed(name: str, domain: str = "") -> Company | None:
    url = f"https://www.indeed.com/cmp/{name}" 
    r = hrequests.get(
        url,
        timeout=QUERY_TIMEOUT,
    )

    if not r.ok:
        log.error(f"Couldn't get results for {r.url}: {r.reason}")
        return None

    name_found = r.html.find("div[@itemprop='name']")
    if not name_found or all([name_found.text.lower() != n.lower() for n in (name, domain)]):
        log.debug(f"Company name found {name_found} doesn't match name given {name}")
        return None

    cmp: Company = Company(name=name_found.text, sameAs={r.url, })
    logo = r.html.find("[@data-tn-component] img")
    if logo and "placeholder" not in logo.attrs['src']:
        cmp['logo'] = urllib.parse.urljoin(url, logo.attrs['src'])
        cmp['image'] = {cmp['logo'], }

    location = r.html.find("li[@data-testid='companyInfo-headquartersLocation'] span")
    if location:
        cmp['location'] = {location.text, }

    numberOfEmployees = r.html.find("li[@data-testid='companyInfo-employee'] div:last-child")
    if numberOfEmployees:
        cmp['numberOfEmployees'] = '-'.join(numberOfEmployees.text.split(" to ")).replace(',', '')

    industry = r.html.find("a[@data-tn-element='industryInterLink']")
    if industry:
        cmp['industry'] = {industry.text, }

    url = r.html.find("a[@data-tn-element='companyLink[]']")
    if url:
        cmp['url'] = url.attrs['href']
        cmp['sameAs'].add(cmp['url'])

    foundingDate = r.html.find("li[data-testid='companyInfo-founded'] div:last-child")
    if foundingDate:
        cmp['foundingDate'] = foundingDate.text

    revenue = r.html.find("li[@data-testid='companyInfo-revenue'] span")
    if revenue:
        cmp['revenue'] = revenue.text

    description = r.html.find("div[@data-testid='more-text'] p") or r.html.find("div[@data-testid='less-text'] p:first-child")
    if description:
        cmp['description'] = {description.text.removesuffix('...Show less'), }

    return cmp


async def company_from_linkedin(name: str, domain: str = "") -> Company | None:
    normalized = normalize(name)
    r = hrequests.get(
        f"https://www.linkedin.com/company/{normalized}",
        timeout=QUERY_TIMEOUT,
        #verify=False,
        #proxies={'https': HTTP_PROXY,
        #         'http': HTTP_PROXY},
    )

    if not r.ok:
        log.error(f"Couldn't get results for {r.url}: {r.reason}")
        return None

    name_found = r.html.find("h1")
    if not name_found or all([name_found.text.lower() != n.lower() for n in (name, domain)]):
        log.debug(f"Company name found {name_found} doesn't match name given {name}")
        return None

    ld_json = json.loads(r.html.find("script[type='application/ld+json']").text)
    try:
        cmp: Company = Company(
            name=ld_json['name'],
            sameAs={ld_json['url'], },
        )
    except TypeError as e:
        log.warning(e)
        return None

    if 'numberOfEmployees' in ld_json:
        cmp['numberOfEmployees'] = str(ld_json['numberOfEmployees']['value'])

    if 'logo' in ld_json:
        cmp['logo'] = ld_json['logo']['contentUrl']
        cmp['image'] = {ld_json['logo']['contentUrl'], }
        
    if 'sameAs' in ld_json:
        cmp['url'] = ld_json['sameAs']

    slogan = ld_json.get('slogan')
    if slogan:
        cmp['description'] = {slogan, }

    if 'address' in ld_json:
        if 'addressRegion' in ld_json:
            location = (
                ld_json['address'].get('addressLocality', ''),
                ld_json['address'].get('addressRegion', ''),
                ld_json['address'].get('addressCountry', '')
                )
        else:
            location = (
                ld_json['address'].get('addressLocality', ''),
                ld_json['address'].get('addressCountry', '')
                )
        if location:
            cmp['location'] = {', '.join(location), }
            if ('streetAddress', 'postalCode', 'addressRegion') in ld_json['address']:
                cmp['address'] = {f"{ld_json['address']['streetAddress']}, {ld_json['address']['postalCode']} {ld_json['address']['addressLocality']}, {ld_json['address']['addressRegion']}, {ld_json['address']['addressCountry']}", },

    if 'description' in ld_json:
        if 'description' not in cmp:
            cmp['description'] = set()
        cmp['description'].add(ld_json['description'])

    return cmp


async def company_from_crunchbase(name: str, domain: str = "") -> Company | None:
    r = hrequests.get(
        f"https://www.crunchbase.com/organization/{name}",
        timeout=QUERY_TIMEOUT,
        #proxies=HTTP_PROXY,
        browser=random.choice(("firefox", "chrome")),
        os=random.choice(("win", "lin", "mac"))
    )

    if not r.ok:
        log.error(f"Couldn't get results for {r.url}: {r.reason}")
        return None

    name_found = r.html.find("h1.profile-name").text.lower()
    if not name_found or all([name_found != n.lower() for n in (name, domain)]):
        log.debug(f"Company name found {name_found} doesn't match name given {name}")
        return None


    cmp: Company = Company(
        name=name,
        description={r.html.find("span.description").text, },
    )

    cmp['sameAs'] = {r.url, }

    summary = r.html.find_all("ul.icon_and_value > li.ng-star-inserted")
    if len(summary) >= 2:
        cmp['location'] = {summary[0].text, }
        cmp['numberOfEmployees'] = summary[1].text
        cmp['url'] = summary[-2].find('a').attrs['href']
        cmp['sameAs'].add(summary[-2].find('a').attrs['href'])

    details_html = r.html.find_all("profile-section.ng-star-inserted li.ng-star-inserted")
    details_fields = {
        "Industries": {
            'field' : 'industry',
            'extract': lambda f: set(str.splitlines(f)),
        },
        "Founded Date": {
            'field': 'foundingDate',
            'extract': str,
        },
        "Founders": {
            'field': 'founder',
            'extract': lambda f: f.split(', '),
        },
        "Also Known As": {
            'field': 'alternateName',
            'extract': lambda f: {f, },
        },
        "Legal Name": {
            'field': 'legalName',
            'extract': str,
        },
        "Contact Email": {
            'field': 'email',
            'extract': str,
        },
        "Phone Number": {
            'field': 'telephone',
            'extract': str,
        },
    }
    for detail in details_html:
        if not detail.text:
            break
        field, value = detail.text.split('\n', 1)
        if field in details_fields.keys():
            cmp[details_fields[field]['field']] = details_fields[field]['extract'](value)

    image = r.html.find(".image-holder img")
    if image:
        cmp['image'] = image.attrs['src']

    sameAs = {e.attrs['href'] for e in r.html.find_all('a[title^="View on"]')}
    if sameAs:
        cmp['sameAs'] |= sameAs

    return cmp
