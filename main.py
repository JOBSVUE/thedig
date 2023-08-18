#!/bin/python3

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
from gemway.__about__ import (
    __version__,
    __title__,
    __summary__,
    __copyright__,
    __author__,
    __email__,
    __license__,
    __version__
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logger_from_settings(log_level=settings.log_level)
    await FastAPILimiter.init(await setup_cache(settings))
    yield

# routing composition
app = FastAPI(
    debug=bool(settings.log_level == "DEBUG"),
    title=__title__,
    summary=__summary__,
    version=__version__,
    contact={"name": f"{__author__} - {__copyright__}", "email": __email__},
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
