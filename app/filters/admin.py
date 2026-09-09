"""
Фильтр «пользователь — администратор».

Использование:
    @router.message(Command("stats"), IsAdmin())
    async def stats(message: Message): ...

Источник истины — data["is_admin"], которое кладёт UserMiddleware (учитывает и ADMIN_USER_IDS,
и админов, распознанных по ADMIN_USERNAMES). Если middleware не отработал (нестандартный тип
апдейта), проверяем только ID из настроек.

В отличие от проверки внутри хендлера, фильтр не перехватывает апдейт у остальных роутеров:
если пользователь не админ, хендлер просто не совпадает и сообщение идёт дальше.
"""
from typing import Optional, Union

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.config import settings


class IsAdmin(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery], is_admin: Optional[bool] = None, **kwargs) -> bool:
        if is_admin is not None:
            return is_admin
        return bool(event.from_user) and settings.is_admin(event.from_user.id)
