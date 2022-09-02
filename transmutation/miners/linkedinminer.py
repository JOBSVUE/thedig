#!/bin/python3
"""
Mine public data from LinkedIn with an email address using Google Search API
Return format is JSON-LD simplified
"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__license__ = "AGPL"

import requests
import json
import logging
import threading

log = logging.getLogger(__name__)

class LinkedInSearchMiner:
    """"
    Mine public data from LinkedIn with an email address using Google Search API and Microsoft Bing API
    """

    GOOGLE_SEARCH_URL_BASE = "https://www.googleapis.com/customsearch/v1/siterestrict"
    BING_SEARCH_URL_BASE = "https://api.bing.microsoft.com/v7.0/custom/search"
    NUM_RESULT = 1
    GOOGLE_FIELDS = "items(title,link,pagemap/cse_image,pagemap/cse_thumbnail,pagemap/metatags/profile:first_name,pagemap/metatags/profile:last_name)"

    def __init__(self, google=True, bing=True, google_api_key:str=None, google_cx:str=None, bing_api_key:str=None, bing_customconfig:str=None):
        
        self.google = False
        self.bing = False

        if google:
            self.google = True
            self.google_api_key = google_api_key
            self.google_cx = google_cx
            self.google_search_url = self.GOOGLE_SEARCH_URL_BASE + "?key=" + google_api_key + "&cx=" + google_cx + "&num=" + str(self.NUM_RESULT) + "&fields=" + self.GOOGLE_FIELDS
            log.debug("Build Google search URL : "+self.google_search_url)

        if bing: 
            self.bing = True
            self.bing_customconfig = bing_customconfig
            self.bing_api_key = bing_api_key
            self.bing_search_url = self.BING_SEARCH_URL_BASE + "?customconfig=" + bing_customconfig + "&count=" + str(self.NUM_RESULT)
            log.debug("Build Bing search URL : "+self.bing_search_url)
        
        if not bing and not google:
            raise ValueError("Must choose at least one search engine: bing or google")

        self.card = {}

    def _search_google(self,query:str):
        """Search a query on Google and return the first result

        Args:
            query (string): query string 

        Returns:
            dict: first result
        """
        search_url_complete = self.google_search_url + "&q=" + query
        result_raw = requests.get(search_url_complete).json()

        # if a data is missing, that means probably that there is no results
        if 'items' in result_raw and len(result_raw['items'])>0:
            return result_raw['items'][0] 
        
        log.debug("No results found for query %s " % query)

    def _search_bing(self, query:str):
        """Search a query on Bing and return the first result

        Args:
            query (str): _description_
        """
        search_url_complete = self.bing_search_url + "&q=" + query
        result_raw = requests.get(search_url_complete,headers={"Ocp-Apim-Subscription-Key" : self.bing_api_key}).json()
        # if a data is missing, that means probably that there is no results
        if 'webPages' in result_raw and 'value' in result_raw['webPages'] and len(result_raw['webPages']['value'])>0:
            return result_raw['webPages']['value'][0]

        log.debug("No results found for query %s " % query)

    def search(self, name, email:str=None, company:str=None):
        """
        search and return the public data for an email and/or company
        """
        result = {}
        if email:
            log.debug("Searching by name %s and email %s" % (name, email))
            
            if self.bing and self.google:
                # creating threads
                byemail = threading.Thread(target=self.by_email, args=(name,email))
                getlocation = threading.Thread(target=self.get_location, args=(name,email))

                # starting threads
                byemail.start()
                getlocation.start()
            
                # wait until all threads finish
                byemail.join()
                getlocation.join()
            elif self.google:
                self.by_email(name, email)
            elif self.bing:
                self.get_location(name, email)
            result = self.card
            
            #result = self.by_email(name, email)
            #result.update(dict(self.get_location(name,email)))
        if company: 
            log.debug("Searching by name %s and company %s" % (name, company))
            result.update(dict(self.by_company(name, company)))
        return result

    def by_email(self, name:str, email:str):
        """
        search and return the public data for a specific email
        """
        result = self._search_google(email)
        if result:
            try:
                full_title = result['title'].split('|')[0].split(' - ')

                # the full name from the result must be the same that the name itself
                if full_title[0].strip().lower() != name.strip().lower():
                    log.debug(f"The full name {full_title[0]} mined doesn't match the name {name} given as a parameter")
                    return {}

                # those fields are optional
                title = full_title[1] if len(full_title) > 1 else None
                company = full_title[2].strip() if len(full_title) > 2 else None


                self.card.update({
                    'givenName': result['pagemap']['metatags'][0]['profile:first_name'],
                    'familyName': result['pagemap']['metatags'][0]['profile:last_name'],
                    'name': full_title[0],
                    'jobTitle': title,
                    'worksFor': {'name' : company},
                    'image': result['pagemap']['cse_thumbnail'][0]['src'],
                    'url': result['link']   
                })
            except KeyError as e:
                log.debug("Not enough data in the results %s" % e)
                return {}
        else:
            log.debug("No result found")
            return {}

        return self.card


    def by_company(self, name:str, company:str):
        """
        Search and return the public data for a name and company
        """
        result = self._search_google(name+" "+company)        

        if result:  
            try:
                full_title = result['title'].split('|')[0].split(' - ')

                # the full name from the result must be the same that the name itself
                if full_title[0].strip().lower() != name.strip().lower():
                    log.debug("The full name mined doesn't match the name given as a parameter")
                    return {}

                # those fields are optional
                title = full_title[1] if len(full_title)>1 else None
                
                #do not need because we already have it
                #company = full_title[2].strip() if len(full_title)>2 else None
                    
                self.card.update({
                    'givenName' : result['pagemap']['metatags'][0]['profile:first_name'],
                    'familyName' : result['pagemap']['metatags'][0]['profile:last_name'],
                    'name' : full_title[0],
                    'jobTitle' : title,
                    'worksFor' : {'name' : company},
                    'image' : result['pagemap']['cse_thumbnail'][0]['src'],
                    'url' : result['link']
                })
            except KeyError as e:
                log.debug("Not enough data in the results %s" % e)
                return {}
        else:
            log.debug("No result found")
            return {}

        return self.card
 
    #from bs4 import BeautifulSoup
    #def _get_ld_json(url: str) -> dict:
    #    req = requests.get(url)
    #    soup = BeautifulSoup(req.text, "html.parser")
    #    return json.loads("".join(soup.find("script", {"type":"application/ld+json"}).contents))

    def get_location(self, name:str, email:str):
        """get location using Bing search engine and update the personal data accordingly
        Args:
            name (str): _description_
            email (str): _description_
        """
        result = self._search_bing(email)        

        if result:  
            try:
                full_title = result['name'].split('|')[0].split(' - ')

                # the full name from the result must be the same that the name itself
                if full_title[0].strip().lower() != name.strip().lower():
                    log.debug("The full name mined doesn't match the name given as a parameter")
                    return {}

                # those fields are optional
                # title = full_title[1] if len(full_title)>1 else None
                
                #do not need because we already have it
                # company = full_title[2].strip() if len(full_title)>2 else None

                address = result['richFacts'][0]['items'][0]['text'].split(', ')
                    
                self.card.update({
                    #for full JSON-LD conformity
                    #"@context": "http://schema.org",
                    #'@type' :   "@Person",
                    
                    # it may be useful to set these values if they're absent
                    #'name'     : full_title[0],
                    #'jobTitle'      : title,
                    #'company'       : company,
                    #'url'  : result['url'],
                    
                    ## useless thumbnail : 404 Error
                    #'image'    : result['openGraphImage']['contentUrl'],
                    
                    'address'      : {
                        #"@type"    :   "PostalAddress",
                        'addressLocation'   : address[0],
                        'addressRegion'     : address[1],
                        'addressCountry'    : address[2]
                    }  
                })
            except KeyError as e:
                log.debug("Not enough data in the results %s" % e)
                return {}
        else:
            log.debug("No result found")
            return {}

        return self.card

    def image2profile(self, image_url : str):
        """_summary_

        Args:
            image_url (str): _description_
        """
        return None


    def bulk(self, person_data:list):
        """Bulk search

        Args:
            person_data (list): _description_

        Yields:
            _type_: _description_
        """
        for person in person_data:
            yield self.search(**person)


if __name__ == "__main__":
    import sys
    import os

    miner = LinkedInSearchMiner(bing=True, google=False, google_api_key=os.getenv('GOOGLE_API_KEY'), google_cx=os.getenv('GOOGLE_CX'), bing_api_key=os.getenv('BING_API_KEY'), bing_customconfig=os.getenv('BING_CUSTOMCONFIG'))
    print(miner.search(name=' '.join(sys.argv[3:]), email=sys.argv[1], company=sys.argv[2]))