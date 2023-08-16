<a href="https://codeclimate.com/repos/6318a2c7c3233c21f30005a8/maintainability"><img src="https://api.codeclimate.com/v1/badges/18313db5cb56fa2c54e6/maintainability" /></a>

# 🪨➜💎 Gemway API

Enrich data about someone (e.g employee name, title, profile pictures etc.) using determinist, OSINT (Opensource Intelligence) and IA in a privacy-friendly way i.e only public data this person consent to share (no databreach) with the possibility to #OptOut.

## ✨ Features

Business-related data fetched from an email address and full name:
- Given name, Family name
- Job title
- Social Network's URL and LinkedIn's URL
- Profile pictures
- Company's name
- Work's location
- Home's location
- Nationality
- Language spoken

## 🛡️ Privacy-by-design

This program intend to be actively GDPR compliant and respectful of person's privacy. Our main goal is to help user's enrich data on existing contacts. We implemented proactively a few GDPR principles in the code itself:
- Right to Opt-Out: if the person mined use the tag #OptOut in its social profile, the enrichment will be stopped, the person's graph won't be enriched and the API's user will be noticed that the person OptOut.
- Lawfulness, fairness and transparency: our sources of data are only public data the person already consent to share publicly. We do not mine databreached data nor doxing for examples. 
- Purpose and data limitation: This program intend to limit extracted personal data to only relevant to business purposes by selecting fields related to business targeting. Sensitive data are not mined.
- Accuracy: we rather prefer not to enrich with dubious information than take the risk of false positives, for examples the social profiles found are checked to be the ones about the person itself.
- Storage limitation: the data enriched are not stored except for cache purpose for a limited duration (default 24 hours)

## 🏗️ How to use

You'll need python 3.11, redis for cache and a [few bunch of libraries](requirements.txt).

### Configure
To run this project, you'll need a few environement variables which includes some API keys. Please edit [default.env](default.env) and rename it as `.env`.

You'll need a few API keys, at least Google Custom Search API and Google Vision.
- [Create a custom search engine](https://cse.google.com/cse/all)  by specifying "\*.linkedin.com" as restricted sites to search on. Once created note the *ID* created and set it in the `.env` file as `GOOGLE_CX` variable. Then you'll need an [API key](https://developers.google.com/custom-search/v1/overview#api_key). 
- Run `setup_google.sh` to set-up automatically Google Vision API. By default, the project will be gemway and so the API key. If you wish to change defaults, feel free to modify the script by yourself. You could also do it manually by doing the following steps:
  1. Visit https://console.developers.google.com and create a project.
  2. Visit https://console.developers.google.com/apis/library/customsearch.googleapis.com and enable "Custom Search API" for your project.
  3. Visit https://console.developers.google.com/apis/credentials and generate API key credentials for your project.


### Launch
Download it and:
```bash
  docker-compose up -d
```

## ⚠️ Support

For support, email contact@ankaboot.fr or join our Matrix channel.


## 📃 License

This software is a free software (open source) [dual-licensed](DUAL-LICENSE) under the [AGPL](LICENSE) and a [commercial license](DUAL-LICENSE).
