"""
Middlewares package
"""
from aiogram import Dispatcher

from .logging import LoggingMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """Настройка всех middleware"""
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
