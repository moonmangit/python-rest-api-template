from fastapi import APIRouter

from app.features.users.presentation.router import router as users_router

router = APIRouter()
router.include_router(users_router)
