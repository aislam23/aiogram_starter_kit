"""
Middleware для работы с пользователями
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from loguru import logger

from app.database import db


class UserMiddleware(BaseMiddleware):
    """Middleware для автоматического сохранения пользователей"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из события
        user: User = data.get("event_from_user")
        
        if user and not user.is_bot:
            try:
                # Сохраняем/обновляем пользователя в базе данных
                await db.add_user(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
            except Exception as e:
                logger.error(f"Ошибка при сохранении пользователя {user.id}: {e}")
        
        # Продолжаем обработку
        return await handler(event, data) 