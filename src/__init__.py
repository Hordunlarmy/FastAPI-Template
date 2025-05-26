from fastapi import APIRouter

from .core.database import Database
from .core.logger import Logger
from .core.response import CustomError  # noqa
from .core.router import core

logger = Logger("app").get_logger()
database = Database()

router = APIRouter(prefix="/api")
router.include_router(core)
