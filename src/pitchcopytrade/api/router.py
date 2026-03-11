from fastapi import APIRouter

from pitchcopytrade.api.routes.author import router as author_router
from pitchcopytrade.api.routes.app import router as app_router
from pitchcopytrade.api.routes.admin import router as admin_router
from pitchcopytrade.api.routes.auth import router as auth_router
from pitchcopytrade.api.routes.public import router as public_router
from pitchcopytrade.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(public_router)
api_router.include_router(app_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(author_router)
api_router.include_router(system_router)
