"""
Статус бота в личном чате: пользователь заблокировал / разблокировал бота.

Telegram присылает my_chat_member сразу, без обращения к пользователю — это основной
и самый дешёвый способ узнать о блокировке. Подстраховка: 403 при рассылке и LivenessService.
"""
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import KICKED, MEMBER, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated
from loguru import logger

from app.database import db

router = Router(name="chat_member")


# Голые маркеры (не переход old >> new): фильтр смотрит только на новый статус,
# поэтому MEMBER срабатывает и на первый /start. Запись идемпотентна, это безопасно.
@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED), F.chat.type == ChatType.PRIVATE)
async def bot_blocked(event: ChatMemberUpdated) -> None:
    """Пользователь заблокировал бота"""
    await db.set_bot_blocked(event.from_user.id, True)
    logger.info(f"🚫 Пользователь {event.from_user.id} заблокировал бота")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER), F.chat.type == ChatType.PRIVATE)
async def bot_unblocked(event: ChatMemberUpdated) -> None:
    """Пользователь разблокировал бота"""
    await db.set_bot_blocked(event.from_user.id, False)
    logger.info(f"✅ Пользователь {event.from_user.id} разблокировал бота")
