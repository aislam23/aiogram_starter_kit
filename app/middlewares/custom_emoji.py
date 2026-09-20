"""
Session-middleware custom emoji: иконки из пака tgiosicons во всех исходящих сообщениях.

Хендлеры пишут обычные эмодзи (см. app/ui/icons.py). Здесь на выходе:
- text/caption → emojify() (только при parse_mode=HTML и без явных entities);
- inline reply_markup → iconify_markup() — у любого метода, где поле есть.

Право на custom emoji (Telegram Premium у владельца) определяется по живому трафику:
если Telegram вернул сообщение без custom_emoji entity или отверг метод с иконками —
статус выключается на RETRY_AFTER, бот шлёт обычные эмодзи, админам уходит уведомление.
По истечении RETRY_AFTER (или после рестарта) иконки пробуются снова — продление Premium
подхватывается без вмешательства.
"""
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response, TelegramType
from loguru import logger

from app.config import settings
from app.database import db

RETRY_AFTER = timedelta(hours=24)


class CustomEmojiStatus:
    """Есть ли сейчас право на custom emoji. Один на процесс (custom_emoji_status)"""

    def __init__(self) -> None:
        self.disabled_at: Optional[datetime] = None
        self.reason: Optional[str] = None
        self.notify_task: Optional[asyncio.Task] = None  # держим ссылку, иначе GC отменит задачу

    @property
    def enabled(self) -> bool:
        return self.disabled_at is None or datetime.now(UTC) - self.disabled_at >= RETRY_AFTER

    @property
    def retry_in(self) -> Optional[timedelta]:
        """Сколько осталось до следующей попытки включить иконки; None — иконки включены"""
        if self.enabled:
            return None
        return RETRY_AFTER - (datetime.now(UTC) - self.disabled_at)

    def disable(self, reason: str, bot: Optional[Bot]) -> bool:
        """Выключить иконки на RETRY_AFTER. No-op, если уже выключены. bot=None — без уведомления"""
        if not self.enabled:
            return False
        self.disabled_at = datetime.now(UTC)
        self.reason = reason
        logger.warning(f"Custom emoji выключены на {RETRY_AFTER}: {reason}")
        if bot is not None:
            self.notify_task = asyncio.create_task(notify_admins(bot, reason), name="custom-emoji-notify")
        return True

    def cancel_notify(self) -> None:
        if self.notify_task is not None and not self.notify_task.done():
            self.notify_task.cancel()
        self.notify_task = None

    def reset(self) -> None:
        self.cancel_notify()
        self.disabled_at = None
        self.reason = None

    def describe(self) -> tuple[str, str]:
        """(режим, пояснение) для /admin: («premium», «») / («обычные эмодзи», « (…)») / («выключены», « (…)»)"""
        if settings.custom_emoji == "off":
            return "выключены", " (CUSTOM_EMOJI=off)"
        if self.enabled:
            return "premium", ""
        hours = max(1, int(self.retry_in.total_seconds() // 3600))
        return "обычные эмодзи", f" (Premium не активен, проверим снова через {hours} ч)"


custom_emoji_status = CustomEmojiStatus()


async def notify_admins(bot: Bot, reason: str) -> None:
    """Сообщить админам (из настроек и назначенным через бота), что иконки выключены"""
    hours = int(RETRY_AFTER.total_seconds() // 3600)
    text = (
        "⚠️ <b>Иконки переключены на обычные эмодзи</b>\n\n"
        f"Telegram не принял custom emoji ({reason}). Обычно это значит, что у владельца бота "
        f"закончился Telegram Premium. Проверим снова через {hours} ч."
    )
    admin_ids = set(settings.admin_user_ids)
    try:
        admin_ids.update(admin.id for admin in await db.get_admins())
    except Exception as e:
        logger.warning(f"Не удалось получить список админов из базы: {e}")
    for admin_id in sorted(admin_ids):
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа {admin_id} о custom emoji: {e}")


class CustomEmojiMiddleware(BaseRequestMiddleware):
    """Подменяет юникод-эмодзи на custom emoji во всех исходящих сообщениях"""

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        return await make_request(bot, method)
