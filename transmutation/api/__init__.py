__license__ = "AGPL"
__author__ = "Badreddine Lejmi <badreddine@ankaboot.fr>"
__version__ = "0.1dev"

# import API
from .transmuter import router as transmuter_router

# finally API router
from fastapi import APIRouter

router = APIRouter()
router.include_router(transmuter_router)
