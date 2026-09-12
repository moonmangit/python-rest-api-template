from fastapi import APIRouter

from app.features.auth.presentation.router import router as auth_router
from app.features.todo.presentation.admin_router import router as admin_todos_router
from app.features.todo.presentation.router import router as todos_router
from app.features.user.presentation.router import router as user_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(todos_router)
router.include_router(admin_todos_router)
