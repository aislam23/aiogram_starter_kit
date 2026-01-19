"""
Handlers package
"""
from aiogram import Dispatcher

from .start import router as start_router
from .help import router as help_router
from .admin import combined_router as admin_router


def setup_routers(dp: Dispatcher) -> None:
    """Настройка всех роутеров"""
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(help_router)
