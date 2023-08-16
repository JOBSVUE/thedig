#!/bin/python3
"""
Microservices for data enrichment using determinist, IA and legit OSINT techniques on your contacts
"""

# fast api
from contextlib import asynccontextmanager
from fastapi import FastAPI, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter

from gemway.api.config import settings, setup_cache

from gemway.api.logsetup import setup_logger_from_settings

# import other apis
from gemway.api import transmuter_router
from gemway.security import get_api_key

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logger_from_settings(log_level=settings.log_level)
    await FastAPILimiter.init(await setup_cache(settings, 8))
    yield

# routing composition
app = FastAPI(
    title="Gemway API",
    description=__doc__,
    version=__version__,
    contact={"name": __copyright__, "email": __author__.split("<")[1][:-1]},
    license_info={"name": __license__},
    dependencies=[Security(get_api_key)],
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    #    allow_origins=origins,
    allow_credentials=True,
)

app.include_router(transmuter_router)

# launching this app as a module is for dev purpose
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        port=settings.server_port,
        host="0.0.0.0",
        reload=True,
    )
