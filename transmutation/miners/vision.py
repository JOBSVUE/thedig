#!/bin/python3
"""
Find social profiles from the image profile using Google Vision (Lens) API

Google Vision API Limits:
- 1800 requests/minute
- 8000 simultaneous requests
"""

import re
import urllib
from random import choice
from typing import Optional

from ..api.config import settings

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from google.cloud import vision
from loguru import logger as log
from thefuzz import fuzz
# JSON Schema.org types
from pydantic_schemaorg.Person import Person

# generic social profile matcher
# Hypothesis: TLD is max 10 characters
# Hypothesis: subdomain is www or a 2-char country code (linkedin) or nothing
# Hypothesis: some social profiles have specific URI for users profiles like
# - in: linkedin
# - person: crunchbase
# - @: tiktok (without trailing /)
# - add: snapchat
generic_socialprofile_regexp = r"^https:\/\/(?P<subdomain>www|\w{2}\.)?(?P<socialnetwork>\w+)\.(?P<TLD>\w{2,10})(\/(in|people|add))?\/@?(?P<identifier>\w+)"
generic_socialprofile_regexp = re.compile(generic_socialprofile_regexp)

MAX_RETRY = 3
MAX_VISION_RESULTS = 20
TOKEN_RATIO = 96


def find_pages_with_matching_images(
        image_url: str,
        max_results: int = MAX_VISION_RESULTS
        ) -> list[str]:
    """Find pages with matching images

    Args:
        image_url (str): image url

    Raises:
        Exception: Google Vision Error

    Returns:
        list[str]: list of urls
    """
    # search using google vision
    client = vision.ImageAnnotatorClient.from_service_account_file(settings.google_vision_credentials)
    response = client.annotate_image({
        'image': {'source': {'image_uri': image_url}},
        'features': [{
            'type_': vision.Feature.Type.WEB_DETECTION,
            'max_results': 20
            }]
    })
    response = response.web_detection

    if hasattr(response, "error"):
        log.error(f"Image: {image_url}. Error: {response.error.message}")
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))

    return [page.url for page in response.pages_with_matching_images]

def find_socialprofiles_matches(image_url: str):
    pages = find_pages_with_matching_images(image_url)
    matched_urls = {}
    for page in pages:
        url_matched = re.match(generic_socialprofile_regexp, page.url)     
        if url_matched:
            matched_urls[page.url] = url_matched.groupdict()

    return matched_urls

def random_ua_headers():
    """
    generate a random user-agent
    basic techniques against bot blockers
    """
    ua = UserAgent(num_newest_uas=1)
    return {"user-agent": ua.random}

def is_valid_socialprofile(url, name, retry=0, max_retry=MAX_RETRY):
    if retry>max_retry:
        return None
  
    # a private life is a happy life
    params = {
        "headers": random_ua_headers(),
        "timeout": 1,
    }
    
    # linkedin is giving us an hard time
    # if retry>0:
    #    params["proxies"] = rotating_proxy()
    #    params['proxies'] = {'http' : "https://localhost:8080"}
    #    log.info(f"Retry with proxy. Proxy: {params['proxies']}, URL: {url}")
        
    try:
        r = requests.get(url, **params)
    except requests.exceptions.ProxyError as e:
        log.warning(f"Proxy error, let's retry. Params: {params}. Error {e}")
        return is_valid_socialprofile(url, name, retry=retry+1)
        #log.error(f"Too much proxy retry. Proxy: {param['proxies']['http']}")
    except requests.exceptions.ConnectTimeout:
        log.warning(f"Timeout error, let's retry. Params: {params}")
        if params.get("proxies"):
            return is_valid_socialprofile(url, name, retry=retry+1)
        return None
    except requests.RequestException as e:
        log.error(f"Failed trying to reach Social Network. URL: {url}, Error: {e}")
        return None

    if not r.ok:
        log.debug(f"Social Network profile not found. URL: {url}, Error: {r.status_code}")
        return False
    
    #soup = BeautifulSoup(r.text, "html.parser", parse_only=parse_only_title)
    soup = BeautifulSoup(r.text, "html.parser")

    # the title from the profile must contains the person's name itself
    title = soup.title

    # something went wrong with scraping?
    if not title:
        log.warning(f"No title, possible antibot tactic. URL: {url}, Headers: {params}, Content: {r.text}")
        return is_valid_socialprofile(url, name, retry=retry+1)     

    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_title = og_title['content'] if og_title else None
    
    # 96 seems a good ratio for difference between ascii and latin characters
    # should do fine tuning here trained on a huge international dataset
    ratio_title = fuzz.partial_token_sort_ratio(name, title.string)
    ratio_ogtitle = fuzz.partial_token_sort_ratio(name, og_title)
    if  ratio_title < TOKEN_RATIO and ratio_ogtitle < TOKEN_RATIO and not name in title.string:
        log.debug(f"Name doesn't match with page title. Name: {name}, URL: {url}, Page title: {title.string} - {ratio_title}, OG Title {og_title} - {ratio_ogtitle}")
        return False

    return soup

def extract_socialprofile(soup, url, name):
    og_image_tag = soup.find("meta", attrs={"property": "og:image"})
    if og_image_tag:
        og_image = og_image_tag.content
        og_image_url = urllib.parse.urljoin(url, og_image)
        log.debug(f"og:image found. Name: {name}, URL: {url}, Image URL: {og_image_url}")

    twitter_image_tag = soup.find("meta", attrs={"property": "twitter:image"})
    if twitter_image_tag:
        twitter_image = twitter_image_tag.content
        twitter_image_url = urllib.parse.urljoin(url, twitter_image)
        log.debug(f"twitter:image found. Name: {name}, URL: {url}, Image URL: {twitter_image_url}")

    og_description = soup.find("meta", attrs={"property": "og:description"})
    if og_description:
        og_description = og_description.content
        log.debug(f"og_description found. Name: {name}, URL: {url}, Image URL: {og_description}")

    schemaorg_name = soup.find("meta", attrs={"property": "name"})
    if schemaorg_name:
        schemaorg_name = schemaorg_name.get("content")
        log.debug(f"Schema.org Name found. Name: {name}, URL: {url}, Schema.org Name: {schemaorg_name}")

    location = soup.find("div", class_="profile-location")
    if location:
        location = location.contents[3].text
        log.debug(f"Location {location}")

class SocialNetworkMiner:
    """Mine for social network profiles related to a person
    """

    # supported social networks and theirs urls
    socialnetworks_urls = {
        # 'crunchbase': "https://crunchbase.com/person/{identifier}",
        'facebook': "https://www.facebook.com/{identifier}",
        'github': "https://github.com/{identifier}",
        'instagram': "https://instagram.com/{identifier}",
        # linkedin don't let you scrap at all :(
        #'linkedin': "https://linkedin.com/in/{identifier}",
        'pinterest': "https://pinterest.com/{identifier}",
        'snapchat':  "https://snapchat.com/add/{identifier}",   
        'telegram': "https://telegram.me/{identifier}",
        'tiktok':  "https://tiktok.com/@{identifier}",
        # twitter is full javascript, needs a headless browser
        'twitter': "https://twitter.com/{identifier}",
        #"twitter#alt": "https://instalker.org/{identifier}",
        "twitter#alt": "https://nitter.it/{identifier}",
        'youtube': "https://youtube.com/{identifier}",
    }

    def __init__(self, person: Person, socialnetworks: Optional[list] = None):
        self.person = person
        self.identifiers = {person.identifier} if person.identifier else set()
        if not self.person.sameAs:
            self.person.sameAs = []
        self.profiles = {}

        # one could choose to opt out some social networks
        if socialnetworks:
            self.socialnetworks_urls = {
                sn: url for sn, url in self.socialnetworks_urls.items() if sn.split("#alt")[0] in socialnetworks
                }
            self.socialnetworks = socialnetworks
        else:
            self.socialnetworks = self.socialnetworks_urls.keys()
        
    def image(self) -> dict:
        """Look for social profiles using profile picture

        Returns:
            dict: dict of profiles urls by social network
        """
        matches = self._image_socialprofiles_matches()
        self.profiles.update({m["socialnetwork"]: url for url, m in matches.items()})
        self.person.sameAs = list(matches.keys())
        return self.profiles

    def identifier(self) -> dict:
        """Look for social profiles using identifier

        Returns:
            dict: dict of profiles urls by social network
        """
        self._generate_identifiers()
        self._generate_urls()
        for idr, urls in self._generated_urls.items():
            for sn, url in urls.items():
                # validate alternative mirror only if it exists
                if f"{sn}#alt" in self.socialnetworks_urls:
                    continue
                soup = is_valid_socialprofile(url, self.person.name)
                if soup:
                    # replace alternative mirror URL with the original one
                    if sn.endswith("#alt"):
                        sn = sn.removesuffix("#alt")
                        url = self.socialnetworks_urls[sn].format(identifier=idr)
                    self.profiles[sn] = url
                    self.person.sameAs.append(url)
                    #extract_socialprofile(soup, url, self.person.name)

        return self.profiles

    def _image_socialprofiles_matches(self):
        pages = find_pages_with_matching_images(self.person.image)
        matched_urls = {}
        for page_url in pages:
            url_matched = re.match(generic_socialprofile_regexp, page_url)     
            if url_matched and url_matched["socialnetwork"] in self.socialnetworks_urls:
                matched_urls[url_matched.group(0)] = url_matched.groupdict()
        return matched_urls
        
    def _generate_urls(self):
        self._generated_urls = {
            idr: {sn: url.format(identifier=idr) for sn, url in self.socialnetworks_urls.items()}
            for idr in self.identifiers
        }
        return self._generated_urls

    def _generate_identifiers(self):
        # add typical identifier from email
        if self.person.email:
            id_email = self._generate_identifier_from_email()
            if id_email:
                self.identifiers.add(id_email)

        # generate *potential* identifier from name
        # useless alone: false positives
        # if self.person.name:
        #    self.identifiers.add(
        #        self._generate_identifier_from_name()
        #    )

        # extract identifier from social profiles
        urls = []
        if self.person.url:
            urls.append(self.person.url)
        if self.person.sameAs:
            urls.extend(self.person.sameAs)

        for url in urls:
            url_matched = re.match(generic_socialprofile_regexp, url)
            if url_matched and url_matched['identifier']:
                self.identifiers.add(url_matched['identifier'])

    def _generate_identifier_from_name(self):
        return self.person.name.encode("ASCII", "ignore").strip().lower().decode().replace(' ', '')

    def _generate_identifier_from_email(self):
        id_email = self.person.email.split('@')[0].replace('.', '').replace('-', '')
        # useful only if really different from name
        # otherwise, it gives too much false positive
        if fuzz.partial_token_sort_ratio(id_email, self.person.name) > 81:
            return None
        return id_email
        
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
                    prog='Vision Miner',
                    description='Find someone using his profile picture')
    parser.add_argument("-n", "--name")
    parser.add_argument("-i", "--identifier")
    parser.add_argument("-g", "--image")
    parser.add_argument("-e", "--email")
    parser.add_argument("-u", "--url")
    parser.add_argument("-s", "--socialnetwork")
    args = parser.parse_args()
    
    p = Person(name=args.name, identifier=args.identifier, image=args.image, email=args.email, sameAs=[])

    s = SocialNetworkMiner(p, socialnetworks=args.socialnetwork)
    print(s.identifier())