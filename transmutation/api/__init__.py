__license__ = "AGPL"
__author__ = "Badreddine Lejmi <badreddine@ankaboot.fr>"
__version__ = "0.1dev"

from api import linkedin
from api import whoiscompany

# finally API router
from fastapi import APIRouter
router = APIRouter()
router.include_router(whoiscompany.router)
router.include_router(linkedin.router)
