"""
Handlers package.

Порядок include_router имеет значение: апдейт достаётся первому подошедшему роутеру.
Админский идёт первым, чтобы его FSM-состояния перехватывали сообщения раньше общих хендлеров.
"""
from aiogram import Dispatcher

from app.config import settings

from .admin import combined_router as admin_router
from .chat_member import router as chat_member_router
from .help import router as help_router
from .start import router as start_router


def setup_routers(dp: Dispatcher) -> None:
    """Настройка всех роутеров"""
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(help_router)
    dp.include_router(chat_member_router)

    if settings.example_handlers:
        from .examples import router as examples_router
        dp.include_router(examples_router)
