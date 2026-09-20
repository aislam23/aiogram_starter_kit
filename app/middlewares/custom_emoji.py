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

Детекция глобальная: одно сообщение туда, где custom emoji не разрешены (канал,
edit_message_text(inline_message_id=…)), выключит иконки на RETRY_AFTER для всех чатов.
Для шаблона (личка, группы) неактуально — зафиксировано, чтобы не искать «пропавшие иконки».

Ограничение: caption внутри InputMedia (SendMediaGroup, EditMessageMedia) и результаты
AnswerInlineQuery не конвертируются — текст там лежит не в полях метода.
"""
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.client.default import Default
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendInvoice, TelegramMethod
from aiogram.methods.base import Response, TelegramType
from aiogram.types import InlineKeyboardMarkup, Message
from loguru import logger

from app.config import settings
from app.services.admins import notify_admins
from app.ui.icons import emojify, iconify_markup

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
            self.notify_task = asyncio.create_task(notify_custom_emoji_off(bot, reason), name="custom-emoji-notify")
            self.notify_task.add_done_callback(_log_notify_outcome)
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


def _log_notify_outcome(task: asyncio.Task) -> None:
    """Забираем исключение фоновой задачи, иначе asyncio пожалуется в лог при GC"""
    if not task.cancelled() and task.exception() is not None:
        logger.opt(exception=task.exception()).error("Уведомление админов о custom emoji упало")


async def notify_custom_emoji_off(bot: Bot, reason: str) -> None:
    """Сообщить админам, что иконки выключены и почему"""
    hours = int(RETRY_AFTER.total_seconds() // 3600)
    text = (
        "⚠️ <b>Иконки переключены на обычные эмодзи</b>\n\n"
        f"Telegram не принял custom emoji ({reason}). Обычно это значит, что у владельца бота "
        f"нет активного Telegram Premium. Проверим снова через {hours} ч."
    )
    await notify_admins(bot, text)


def _resolve_parse_mode(bot: Bot, method: TelegramMethod) -> Optional[str]:
    """parse_mode метода с учётом дефолта бота; None — у метода нет parse_mode"""
    value = getattr(method, "parse_mode", None)
    if isinstance(value, Default):
        value = bot.default.parse_mode
    # ParseMode — str-Enum: value.upper() даёт "HTML", а str(value) дал бы "ParseMode.HTML"
    return value.upper() if isinstance(value, str) else None


def _convert(bot: Bot, method: TelegramMethod) -> tuple[Optional[TelegramMethod], bool]:
    """(метод с иконками или None, если менять нечего; вставили ли <tg-emoji> в текст)"""
    update: dict = {}
    injected_text = False

    explicit_entities = getattr(method, "entities", None) or getattr(method, "caption_entities", None)
    if _resolve_parse_mode(bot, method) == "HTML" and not explicit_entities:
        for field in ("text", "caption"):
            value = getattr(method, field, None)
            if isinstance(value, str):
                converted = emojify(value)
                if converted != value:
                    update[field] = converted
                    injected_text = True

    markup = getattr(method, "reply_markup", None)
    if isinstance(markup, InlineKeyboardMarkup):
        new_markup, changed = iconify_markup(markup)
        if changed:
            update["reply_markup"] = new_markup

    if not update:
        return None, False
    return method.model_copy(update=update), injected_text


def _has_custom_emoji(message: Message) -> bool:
    entities = (message.entities or []) + (message.caption_entities or [])
    return any(entity.type == "custom_emoji" for entity in entities)


class CustomEmojiMiddleware(BaseRequestMiddleware):
    """Подменяет юникод-эмодзи на custom emoji во всех исходящих сообщениях"""

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        # Инвойс: первая кнопка — Pay, поведение иконок там неизвестно; entities не поддерживаются
        if isinstance(method, SendInvoice) or not custom_emoji_status.enabled:
            return await make_request(bot, method)

        converted, injected_text = _convert(bot, method)
        if converted is None:
            return await make_request(bot, method)

        try:
            result = await make_request(bot, converted)
        except TelegramBadRequest as e:
            if "message is not modified" in e.message:
                # Штатная ошибка (повторное нажатие, тот же прогресс): повтор стёр бы иконки с экрана
                raise
            # Повтор исходным методом: упадёт и он — ошибка не наша, пробрасываем первую.
            # Цена: 2 запроса на каждую 400 при включённых иконках — принято в спеке
            try:
                result = await make_request(bot, method)
            except TelegramBadRequest:
                raise e from None
            custom_emoji_status.disable(f"Telegram отверг сообщение с иконками: {e.message}", bot)
            return result

        if injected_text and isinstance(result, Message) and not _has_custom_emoji(result):
            custom_emoji_status.disable("в ответе Telegram нет custom_emoji entity", bot)
        return result
