<a href="https://codeclimate.com/repos/6318a2c7c3233c21f30005a8/maintainability"><img src="https://api.codeclimate.com/v1/badges/18313db5cb56fa2c54e6/maintainability" /></a>

# 🪨➜💎 Transmutation API

Enrich data about someone (e.g employee name, title, profile pictures etc.) using OSINT (Opensource Intelligence) methods i.e only public data this person consent to share.

## ✨ Features

Data fetched:
- First name, last name, title, profile picture, company name from LinkedIn using Google/Bing Search by email address and full name
- Company's name from an email address using whois on its domain
- Company's logo either favicon or open graph image (used for social networks)


## 🏗️ How to use

You'll need python 3.10 and a [few bunch of libraries](requirements.txt).

### Configure
To run this project, you'll need a few environement variables which includes some API keys. Please edit [default.env](default.env) and rename it as `.env`.

You'll need a few API keys, at least Google Custom Search API and Google Vision.
- [Create a custom search engine](https://cse.google.com/cse/all)  by specifying "\*.linkedin.com" as restricted sites to search on. Once created note the *ID* created and set it in the `.env` file as `GOOGLE_CX` variable. Then you'll need an [API key](https://developers.google.com/custom-search/v1/overview#api_key). 
- Run `setup_google.sh` to set-up automatically Google Vision API. By default, the project will be transmutation and so the API key. If you wish to change defaults, feel free to modify the script by yourself. You could also do it manually by doing the following steps:
  1. Visit https://console.developers.google.com and create a project.
  2. Visit https://console.developers.google.com/apis/library/customsearch.googleapis.com and enable "Custom Search API" for your project.
  3. Visit https://console.developers.google.com/apis/credentials and generate API key credentials for your project.


### Install

```bash
  pip install transmutation
```

### Launch
```bash
  uvicorn transmutation:app
``` 

## ⚠️ Support

For support, email contact@ankaboot.fr or join our Matrix channel.


## 📃 License

This software is a free software (open source) [dual-licensed](DUAL-LICENSE) under the [AGPL](LICENSE) and a [commercial license](DUAL-LICENSE).

