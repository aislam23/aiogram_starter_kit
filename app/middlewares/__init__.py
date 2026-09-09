"""
Middlewares package
"""
from aiogram import Dispatcher

from .logging import LoggingMiddleware
from .user import UserMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """Настройка всех middleware.

    Регистрируем как outer-middleware: они срабатывают на каждый апдейт,
    даже если ни один хендлер его не обработал. Внутренние (dp.message.middleware)
    запускаются только при совпадении с хендлером.
    """
    # Middleware для логирования
    dp.message.outer_middleware(LoggingMiddleware())
    dp.callback_query.outer_middleware(LoggingMiddleware())

    # Middleware для пользователей — сохраняет каждого, кто написал боту
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
