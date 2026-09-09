"""
Middleware для работы с пользователями.

- Сохраняет/обновляет каждого написавшего боту пользователя.
- Определяет, админ ли он, и кладёт результат в data["is_admin"] для фильтров и хендлеров.
- Если username пользователя есть в ADMIN_USERNAMES, а ID ещё не известен — выдаёт права
  и запоминает ID в базе. Username «занимается» один раз: если админ потом сменит имя,
  а старое возьмёт кто-то другой, чужой права не получит.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from loguru import logger

from app.config import normalize_username, settings
from app.database import db


class UserMiddleware(BaseMiddleware):
    """Middleware для автоматического сохранения пользователей и определения админов"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")

        if user and not user.is_bot:
            data["is_admin"] = await self._save_and_check_admin(user)

        return await handler(event, data)

    async def _save_and_check_admin(self, user: User) -> bool:
        is_admin = settings.is_admin(user.id)
        try:
            saved = await db.add_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            is_admin = is_admin or bool(saved.is_admin)

            if not is_admin and settings.is_admin_username(user.username):
                username = normalize_username(user.username)
                claimed_by = await db.get_admin_by_username(username)
                if claimed_by is None or claimed_by.id == user.id:
                    await db.set_admin(user.id, username)
                    is_admin = True
                    logger.info(f"👑 Admin @{username} resolved to user ID {user.id}")
                else:
                    logger.warning(
                        f"⚠️ User {user.id} has admin username @{username}, "
                        f"but it was already claimed by user {claimed_by.id} — not promoting"
                    )
        except Exception as e:
            logger.error(f"Ошибка при сохранении пользователя {user.id}: {e}")

        return is_admin
