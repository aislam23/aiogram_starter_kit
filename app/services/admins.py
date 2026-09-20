"""
Общее для сервисов: уведомление всех админов бота.
"""
from aiogram import Bot
from loguru import logger

from app.config import settings
from app.database import db


async def notify_admins(bot: Bot, text: str) -> None:
    """Отправить текст всем админам: из настроек (ADMIN_USER_IDS) и назначенным через бота.

    Список из базы и каждая отправка — в try/except: админ мог заблокировать бота, база может
    быть недоступна; сообщение остальным всё равно уйдёт, неудачи — в лог.
    """
    admin_ids = set(settings.admin_user_ids)
    try:
        admin_ids.update(admin.id for admin in await db.get_admins())
    except Exception as e:
        logger.warning(f"Не удалось получить список админов из базы: {e}")
    for admin_id in sorted(admin_ids):
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение админу {admin_id}: {e}")
