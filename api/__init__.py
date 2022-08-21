from api import linkedin
from api import whoiscompany
#from api import config

#finally API router
from fastapi import APIRouter
router = APIRouter()
router.include_router(whoiscompany.router)
router.include_router(linkedin.router)