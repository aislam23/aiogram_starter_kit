"""
Middleware для логирования запросов
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from loguru import logger


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех входящих обновлений"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основной метод middleware"""
        
        # Логируем входящие сообщения
        if isinstance(event, Message):
            user = event.from_user
            logger.info(
                f"📥 Message from {user.id} (@{user.username}): "
                f"'{event.text[:50] if event.text else 'No text'}'"
            )
        
        # Логируем callback запросы
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            logger.info(
                f"🔘 Callback from {user.id} (@{user.username}): "
                f"'{event.data}'"
            )
        
        # Выполняем обработчик
        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            logger.error(f"❌ Error in handler: {e}")
            raise
