from fastapi import APIRouter

from app.features.auth.presentation.router import router as auth_router
from app.features.users.presentation.router import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
