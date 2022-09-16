#!/bin/python3
"""
Mine public data from LinkedIn with an email address using Google Search API
Return format is JSON-LD simplified
"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__license__ = "AGPL"

import re
from .ISO3166 import ISO3166
import requests
import logging
import threading

log = logging.getLogger(__name__)

# linkedin profile url with an ISO3166 country code regular expression
LINKEDIN_URL_RE = re.compile("https:\/\/(\w{2})\.?linkedin.com\/in\/w*")


def country_from_url(linkedin_url: str) -> str:
    """Country name based on the xx.linkedin.com profile url where xx is the ISO3166 country code
    else return None

    Args:
        linkedin_url (str): linkedin profile URL

    Returns:
        str: Country name
    """
    match = LINKEDIN_URL_RE.match(linkedin_url)

    if match:
        return ISO3166[match[1].upper()]
    else:
        return None


class LinkedInSearch:
    """ "
    Mine public data from LinkedIn with an email address using Google Search API and/or Microsoft Bing API
    """

    NUM_RESULTS = 1
    GOOGLE_FIELDS = "items(title,link,pagemap/cse_thumbnail,pagemap/metatags/profile:first_name,pagemap/metatags/profile:last_name,pagemap/metatags/og:image)"
    GOOGLE_SEARCH_URL_BASE = "https://www.googleapis.com/customsearch/v1/siterestrict?key={google_api_key}&cx={google_cx}&num{num_results}&fields={google_fields}"
    BING_SEARCH_URL_BASE = "https://api.bing.microsoft.com/v7.0/custom/search?customconfig={bing_custom_config}&count={num_results}"

    def __init__(self, search_api_params: dict, google=True, bing=False):
        """LinkedInSearch constructor

        Args:
            search_api_params (dict): parameters for the search API including credentials
            google (bool, optional): search with Google. Defaults to True.
            bing (bool, optional): search with Bing. Defaults to False.

        Raises:
            ValueError: at least bing or google search engine must be True
        """

        self.google = False
        self.bing = False

        # there is default values for this params, the others are mandatory
        if "num_result" not in search_api_params:
            search_api_params["num_results"] = LinkedInSearch.NUM_RESULTS
        if "google_fields" not in search_api_params:
            search_api_params["google_fields"] = LinkedInSearch.GOOGLE_FIELDS

        if google:
            self.google = True
            self.google_search_url = self.GOOGLE_SEARCH_URL_BASE.format(
                **search_api_params
            )
            log.debug("Build Google search URL : " + self.google_search_url)

        if bing:
            self.bing = True
            self.bing_search_url = self.BING_SEARCH_URL_BASE.format(**search_api_params)
            log.debug("Build Bing search URL : " + self.bing_search_url)

        if not bing and not google:
            raise ValueError("Must choose at least one search engine: bing or google")

        self.card = {}

    def _search_google(self, query: str):
        """Search a query on Google and return the first result

        Args:
            query (string): query string

        Returns:
            dict: first result
        """
        search_url_complete = self.google_search_url + "&q=" + query
        result_raw = requests.get(search_url_complete).json()

        # if a data is missing, that means probably that there is no results
        if "items" in result_raw and len(result_raw["items"]) > 0:
            return result_raw["items"][0]

        log.debug("No results found for query %s " % query)

    def _search_bing(self, query: str):
        """Search a query on Bing and return the first result

        Args:
            query (str): _description_
        """
        search_url_complete = self.bing_search_url + "&q=" + query
        result_raw = requests.get(
            search_url_complete,
            headers={"Ocp-Apim-Subscription-Key": self.bing_api_key},
        ).json()
        log.info("bing result %s" % result_raw)
        # if a data is missing, that means probably that there is no results
        if (
            "webPages" in result_raw
            and "value" in result_raw["webPages"]
            and len(result_raw["webPages"]["value"]) > 0
        ):
            return result_raw["webPages"]["value"][0]

        log.debug("No results found for query %s " % query)

    def _add_country(self):
        """add country name to the Person JSON-LD based on the linkedin profile url"""
        if "url" in self.card:
            country = country_from_url(self.card["url"])
            if country:
                self.card["address"] = {
                    "@type": "PostalAddress",
                    "addressCountry": country,
                }

    def search(self, name, email: str = None, company: str = None):
        """
        search and return the public data for an email and/or company
        """
        result = {}
        if email:
            log.debug("Searching by name %s and email %s" % (name, email))

            if self.bing and self.google:
                # creating threads
                google = threading.Thread(target=self.email_google, args=(name, email))
                bing = threading.Thread(target=self.email_bing, args=(name, email))

                # starting threads
                google.start()
                bing.start()

                # wait until all threads finish
                google.join()
                bing.join()  # usually add location
            elif self.google:
                self.email_google(name, email)
            elif self.bing:
                self.email_bing(name, email)

            self._add_country()

            result = self.card
        if company:
            log.debug("Searching by name %s and company %s" % (name, company))
            result.update(dict(self.by_company(name, company)))
        return result

    def email_google(self, name: str, email: str):
        """
        Google search engine then return and update the personal data accordingly
        Google gives you the givenName/familyName but not the location
        Args:
            name (str): _description_
            email (str): _description_
        """
        result = self._search_google(email)
        if result:
            try:
                full_title = parse_linkedin_title(result["title"])

                # the full name from the result must be the same that the name itself
                if full_title["name"].lower() != name.strip().lower():
                    log.debug(
                        f"The full name {full_title[0]} mined doesn't match the name {name} given as a parameter"
                    )
                    return {}

                self.card.update(
                    {
                        # for full JSON-LD conformity
                        "@context": "http://schema.org",
                        "@type": "@Person",
                        "givenName": result["pagemap"]["metatags"][0][
                            "profile:first_name"
                        ],
                        "familyName": result["pagemap"]["metatags"][0][
                            "profile:last_name"
                        ],
                        "name": full_title["name"],
                        "jobTitle": full_title.get("title"),
                        "worksFor": {"name": full_title.get("company")},
                        # cse_thumbnail is Google's image
                        "image": result["pagemap"]["metatags"][0]["og:image"],
                        "url": result["link"],
                    }
                )
            except KeyError as e:
                log.debug("Not enough data in the results %s" % e)
                return {}
        else:
            log.debug("No result found")
            return {}

        return self.card

    def by_company(self, name: str, company: str):
        """
        Search and return the public data for a name and company
        """
        result = self._search_google(name + " " + company)

        if result:
            try:
                full_title = parse_linkedin_title(result["title"])

                # the full name from the result must be the same that the name itself
                if full_title["name"].lower() != name.strip().lower():
                    log.debug(
                        "The full name mined doesn't match the name given as a parameter"
                    )
                    return {}

                # do not need because we already have it
                # company = full_title[2].strip() if len(full_title)>2 else None

                self.card.update(
                    {
                        "givenName": result["pagemap"]["metatags"][0][
                            "profile:first_name"
                        ],
                        "familyName": result["pagemap"]["metatags"][0][
                            "profile:last_name"
                        ],
                        "name": full_title["name"],
                        "jobTitle": full_title.get("title"),
                        "worksFor": {"name": full_title.get("company")},
                        "image": result["pagemap"]["cse_thumbnail"][0]["src"],
                        "url": result["link"],
                    }
                )
            except KeyError as e:
                log.debug("Not enough data in the results %s" % e)
                return {}
        else:
            log.debug("No result found")
            return {}

        return self.card

    def email_bing(self, name: str, email: str):
        """Bing search engine then return and update the personal data accordingly
        Bing gives you sometimes the location but doesn't give you the givenName/familyName
        Args:
            name (str): _description_
            email (str): _description_
        """
        result = self._search_bing(email)

        if result:
            try:
                # usually a LinkedIn title has this form "Full Name - Title - Company | LinkedIn"
                full_title = parse_linkedin_title(result["name"])

                # the full name from the result must be the same that the name itself
                if full_title["name"].lower() != name.strip().lower():
                    log.debug(
                        "The full name mined doesn't match the name given as a parameter"
                    )
                    return {}

                self.card.update(
                    {
                        # for full JSON-LD conformity
                        "@context": "http://schema.org",
                        "@type": "@Person",
                        # it may be useful to set these values if they're absent
                        "name": full_title["name"],
                        "jobTitle": full_title.get("title"),
                        "worksFor": {"name": full_title.get("company")},
                        "url": result["url"],
                        # sometimes it's an useless thumbnail : 404 Error
                        "image": result["openGraphImage"]["contentUrl"],
                    }
                )

                # Bing also gives you sometimes location
                address = result["richFacts"][0]["items"][0]["text"].split(", ")
                # however sometimes the address isn't correctly identified by Bing
                if len(address) >= 3:
                    self.card.update(
                        {
                            "address": {
                                # "@type"    :   "PostalAddress",
                                "addressLocation": address[0],
                                "addressRegion": address[1],
                                "addressCountry": address[2],
                            }
                        }
                    )
            except KeyError as e:
                log.debug("Not enough data in the results %s" % e)
                return {}
        else:
            log.debug("No result found")
            return {}

        return self.card


def parse_linkedin_title(title):
    """parse LinkedIn Title that has this form
        Full Name - Title - Company | LinkedIn
        and sometimes (Google only):
        Full Name - Title - Company... | LinkedIn
    Args:
        title (str): title from LinkedIn page
    """
    result = {}
    full_title = title.split("|")[0].split(" - ")
    result["name"] = full_title[0]

    if len(full_title) > 1:
        result["title"] = full_title[1]
        if len(full_title) > 2:
            # sometimes the company name has a '...' suffix
            result["company"] = full_title[2].removesuffix("...").strip()
    return result


if __name__ == "__main__":
    import sys
    import os

    log.setLevel(logging.DEBUG)

    search_api_params = {
        "google_api_key": os.getenv("GOOGLE_API_KEY"),
        "google_cx": os.getenv("GOOGLE_CX"),
        "bing_api_key": os.getenv("BING_API_KEY"),
        "bing_customconfig": os.getenv("BING_CUSTOMCONFIG"),
    }
    miner = LinkedInSearch(search_api_params)
    print(
        miner.search(
            name=" ".join(sys.argv[3:]), email=sys.argv[1], company=sys.argv[2]
        )
    )
