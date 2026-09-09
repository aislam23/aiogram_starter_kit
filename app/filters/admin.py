"""
Фильтр «пользователь — администратор».

Использование:
    @router.message(Command("stats"), IsAdmin())
    async def stats(message: Message): ...

В отличие от проверки внутри хендлера, фильтр не перехватывает апдейт у остальных роутеров:
если пользователь не админ, хендлер просто не совпадает и сообщение идёт дальше.
"""
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.config import settings


class IsAdmin(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        return bool(event.from_user) and settings.is_admin(event.from_user.id)
