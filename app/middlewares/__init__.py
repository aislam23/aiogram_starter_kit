"""
Middlewares package
"""
from aiogram import Dispatcher

from .logging import LoggingMiddleware
from .user import UserMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """Настройка всех middleware"""
    # Middleware для логирования
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    # Middleware для пользователей
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
