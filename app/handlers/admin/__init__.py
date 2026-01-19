"""
Admin handlers package
"""
from aiogram import Router

from .admin import router as admin_router
from .api_settings import router as api_settings_router

# Объединяем роутеры
combined_router = Router()
combined_router.include_router(admin_router)
combined_router.include_router(api_settings_router)

__all__ = ["combined_router"]