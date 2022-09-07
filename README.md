
# 🪨➜💎 Transmutation API

Enrich data about someone (e.g employee name, title, profile pictures etc.) using OSINT (Opensource Intelligence) methods i.e only public data this person consent to share.

## Features

Data fetched:
- First name, last name, title, profile picture, company name from LinkedIn using Google/Bing Search by email address and full name
- Company's name from an email address using whois on its domain
- Company's logo either favicon or open graph image (used for social networks)


## How to use

You'll need python 3.10 and a [few bunch of libraries](requirements.txt)

### Install
```bash
  pip install transmutation
```

### Configure
To run this project, you'll need a few environement variables which includes some API keys. Please edit [default.env](default.env) and rename it as `.env`.

### Launch
```bash
  cd transmutation
  guvicorn main:app
``` 


## Support

For support, email contact@ankaboot.fr or join our Matrix channel.


## License

This software is a free software (open source) [dual-licensed](DUAL-LICENSE) under the [AGPL](LICENSE) and a [commercial license](DUAL-LICENSE).

