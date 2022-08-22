#!/bin/python3
"""
Return more infos on company
- logo : favicon of the website or LinkedIn's page logo or Wikipedia's page logo
"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__license__ = "AGPL"

import re
from bs4 import BeautifulSoup
import urllib.parse

import logging
import requests
log = logging.getLogger(__name__)


def guess_favicon(urls, verify_ssl:bool):
    """guess favicon by urls

    Args:
        url (_type_): urls of websites to check
        verify_ssl (bool): ssl verify

    Returns:
        favicon_url: url of favicon
    """
    r = None
    #scanning classic favicon urls
    for url in urls:
        favicon_url = url+"/favicon.ico"
        try:
            r = requests.get(favicon_url, verify=verify_ssl)
        except requests.RequestException:
            log.debug("No reachable favicon for this url: %s" % favicon_url)
            favicon_url = None #no result
            del urls[urls.index(url)]
            continue
        if r.status_code == 200 and r.headers['Content-Type'] == 'image/x-icon':
            log.debug("favicon found by URL guessing")
            return favicon_url
        else:  #yet, this is probably the right website to scan
            log.debug("No favicon yet this url probably hosts the website: %s" % url)
            favicon_url = None #no result though
            urls = [url]
            break

    return favicon_url
    

def scan_favicon(urls, verify_ssl, force_og_image):
    #scanning websites now
    for url in urls:
        try:
            r = requests.get(url, verify=verify_ssl)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, features="lxml")
            log.debug("That page's url seems Ok: %s " % url)
        
            if force_og_image:
                og_image_tag = soup.find("meta", attrs={'property' : "og:image"})
                if og_image_tag:
                    log.debug("og:image found for this url: %s" % url)
                    og_image = og_image_tag.get('content')
                    favicon_url = urllib.parse.urljoin(url, og_image)
                    return favicon_url
                else:
                    log.debug("No og:image for this url: %s" % url)
            
            favicon_link = soup.find('link', attrs={'rel': re.compile("^(shortcut icon|icon)$", re.I)})
            if favicon_link:
                log.debug("We did find the favicon link in the HTML: %s" % favicon_link)
                favicon_href = favicon_link.get("href")
                favicon_url = urllib.parse.urljoin(url, favicon_href)
                return favicon_url    
  
            else:
                log.debug("Nothing found sorry")
        

def get_favicon(domain: str, url: str=None, guess:bool=True, scan:bool=True, verify_ssl:bool=False, force_og_image:bool=True) -> str:
    """return favicon for a domain or url

    Args:
        domain (str): domain name (OR url but not both)
        url (str): url of the website (OR domain but not both)
        guess (bool): guess favicon.ico presence
        scan (bool): scan websites HTML for favicon presence
        verify_ssl(bool): 
        force_og_image (bool): scan websites for og:image metadata if favicon not available
    """

   #parameters check
    try:
        assert guess or scan
    except AssertionError:
        log.debug("neither guess nor scan was True")
        raise ValueError("At least guess or scan must be True")
    try:
        assert not (domain and url)
    except AssertionError:
        log.debug("Must choose between domain and url")
        raise ValueError("Must choose between domain and url")

    #url or domain, not both   
    if not url:
        url = url if url else f"https://www.{domain}"
        urls = [url, url.replace('https://', 'http://'), url.replace('www.',''), url.replace('https://', 'http://').replace('www.','')]
    else:
        urls = [url]

    #guess favicon on https://www and without https or www
    favicon_url = None
    if guess:
        favicon_url = guess_favicon(urls, verify_ssl)
    if favicon_url is None and scan:
        favicon_url = scan_favicon(urls, verify_ssl, force_og_image)
    
    return favicon_url

if __name__ == "__main__":
    import sys
    logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(funcName)s: %(message)s", level=logging.DEBUG)

    log.info(get_favicon(guess=False, domain=sys.argv[1]))
    
