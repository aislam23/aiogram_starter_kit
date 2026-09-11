"""
Сервис рассылки сообщений
"""
import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, Message
from loguru import logger

from app.database import db


class ProgressReporter:
    """
    Обновляет одно сообщение о ходе длинной операции, не упираясь в flood control.

    Telegram ограничивает частоту editMessageText в одном чате. Рассылка на
    десятки тысяч человек дёргает прогресс тысячи раз подряд — без троттлинга
    сообщение через ~40 минут перестаёт обновляться, а каждый новый вызов во
    время flood-wait продлевает бан, так что и финальный отчёт не доходит.

    - `update()` редактирует не чаще `min_interval` секунд и молчит,
      пока действует flood-wait;
    - `finish()` доставляет финальный текст обязательно: ждёт flood-wait,
      повторяет, а если редактирование так и не удалось — шлёт новым сообщением.
    """

    MIN_INTERVAL = 5.0   # секунд между правками прогресса
    FINAL_ATTEMPTS = 3   # попыток доставить финальный отчёт

    def __init__(self, message: Message, min_interval: float = MIN_INTERVAL):
        self.message = message
        self.min_interval = min_interval
        self._last_edit_at = 0.0      # time.monotonic() последней удачной правки
        self._muted_until = 0.0       # time.monotonic(), до которого молчим из-за flood-wait

    async def update(self, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """Обновить прогресс. Возвращает True, если сообщение реально отредактировано."""
        now = time.monotonic()
        if now < self._muted_until:
            return False
        if now - self._last_edit_at < self.min_interval:
            return False

        try:
            await self.message.edit_text(text, reply_markup=reply_markup)
        except TelegramRetryAfter as e:
            self._muted_until = now + e.retry_after + 1
            logger.warning(f"Прогресс: flood-wait {e.retry_after}s, обновления приостановлены")
            return False
        except TelegramBadRequest as e:
            # Обычно "message is not modified" — текст не изменился, это не ошибка
            logger.debug(f"Прогресс не обновлён: {e}")
            return False
        except Exception as e:
            logger.warning(f"Прогресс не обновлён: {e}")
            return False

        self._last_edit_at = now
        return True

    async def finish(self, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
        """Доставить финальный текст: сначала правкой, при неудаче — новым сообщением."""
        if await self._with_flood_wait(lambda: self.message.edit_text(text, reply_markup=reply_markup)):
            return
        logger.warning("Финальный отчёт не удалось вписать в сообщение прогресса, шлём новым")
        await self._with_flood_wait(lambda: self.message.answer(text, reply_markup=reply_markup))

    async def _with_flood_wait(self, call: Callable[[], Awaitable[Any]]) -> bool:
        """Выполнить вызов Telegram, пережидая flood-wait до FINAL_ATTEMPTS раз."""
        for attempt in range(self.FINAL_ATTEMPTS):
            try:
                await call()
                return True
            except TelegramRetryAfter as e:
                logger.warning(
                    f"Финальный отчёт: flood-wait {e.retry_after}s, "
                    f"попытка {attempt + 1}/{self.FINAL_ATTEMPTS}"
                )
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:
                logger.error(f"Финальный отчёт не доставлен: {e}")
                return False
        return False


class BroadcastService:
    """Сервис для рассылки сообщений"""

    # Сколько раз повторять отправку одному пользователю после flood-wait (429)
    MAX_RETRIES = 3

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_broadcast(
        self,
        message: Message,
        custom_keyboard: Optional[InlineKeyboardMarkup] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, int]:
        """
        Отправка рассылки всем живым пользователям (не заблокировавшим бота)

        Args:
            message: Сообщение для рассылки
            custom_keyboard: Кастомная клавиатура
            progress_callback: Функция для отслеживания прогресса

        Returns:
            Словарь со статистикой отправки
        """
        users = await db.get_alive_users()

        stats = {
            "total": len(users),
            "sent": 0,
            "failed": 0,
            "blocked": 0
        }

        logger.info(f"Начинаем рассылку для {len(users)} пользователей")

        # Отправляем сообщения пачками по 30 штук
        batch_size = 30
        delay_between_batches = 1  # секунда между пачками

        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            tasks = []

            for user in batch:
                task = self._send_single_message(
                    user_id=user.id,
                    message=message,
                    custom_keyboard=custom_keyboard
                )
                tasks.append(task)

            # Выполняем пачку параллельно
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Обрабатываем результаты
            for result in results:
                if isinstance(result, Exception):
                    if isinstance(result, TelegramForbiddenError):
                        stats["blocked"] += 1
                    else:
                        stats["failed"] += 1
                elif result:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1

            # Вызываем callback для обновления прогресса
            if progress_callback:
                await progress_callback(stats)

            # Пауза между пачками
            if i + batch_size < len(users):
                await asyncio.sleep(delay_between_batches)

        logger.info(f"Рассылка завершена. Отправлено: {stats['sent']}, Ошибок: {stats['failed']}, Заблокировано: {stats['blocked']}")
        return stats

    async def _send_single_message(
        self,
        user_id: int,
        message: Message,
        custom_keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправка одного сообщения пользователю

        Args:
            user_id: ID пользователя
            message: Сообщение для отправки
            custom_keyboard: Кастомная клавиатура

        Returns:
            True если сообщение отправлено успешно
        """
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return await self._send_once(user_id, message, custom_keyboard)
            except TelegramRetryAfter as e:
                # Flood-wait: Telegram просит подождать. Ждём и повторяем,
                # иначе получатель молча выпал бы из рассылки.
                if attempt >= self.MAX_RETRIES:
                    logger.warning(
                        f"Пользователь {user_id}: flood-wait {e.retry_after}s, "
                        f"попытки исчерпаны ({self.MAX_RETRIES})"
                    )
                    return False
                logger.warning(
                    f"Пользователь {user_id}: flood-wait {e.retry_after}s, "
                    f"повтор {attempt + 1}/{self.MAX_RETRIES}"
                )
                await asyncio.sleep(e.retry_after + 0.5)
        return False

    async def _send_once(
        self,
        user_id: int,
        message: Message,
        custom_keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """Одна попытка отправки. TelegramRetryAfter пробрасывается наверх для повтора."""
        try:
            # Определяем тип сообщения и отправляем соответствующим методом
            if message.text:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message.text,
                    reply_markup=custom_keyboard,
                    parse_mode=message.html_text and "HTML" or None
                )
            elif message.photo:
                await self.bot.send_photo(
                    chat_id=user_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption,
                    reply_markup=custom_keyboard,
                    parse_mode=message.html_text and "HTML" or None
                )
            elif message.video:
                await self.bot.send_video(
                    chat_id=user_id,
                    video=message.video.file_id,
                    caption=message.caption,
                    reply_markup=custom_keyboard,
                    parse_mode=message.html_text and "HTML" or None
                )
            elif message.document:
                await self.bot.send_document(
                    chat_id=user_id,
                    document=message.document.file_id,
                    caption=message.caption,
                    reply_markup=custom_keyboard,
                    parse_mode=message.html_text and "HTML" or None
                )
            elif message.audio:
                await self.bot.send_audio(
                    chat_id=user_id,
                    audio=message.audio.file_id,
                    caption=message.caption,
                    reply_markup=custom_keyboard,
                    parse_mode=message.html_text and "HTML" or None
                )
            elif message.voice:
                await self.bot.send_voice(
                    chat_id=user_id,
                    voice=message.voice.file_id,
                    caption=message.caption,
                    reply_markup=custom_keyboard,
                    parse_mode=message.html_text and "HTML" or None
                )
            elif message.video_note:
                await self.bot.send_video_note(
                    chat_id=user_id,
                    video_note=message.video_note.file_id,
                    reply_markup=custom_keyboard
                )
            elif message.animation:
                await self.bot.send_animation(
                    chat_id=user_id,
                    animation=message.animation.file_id,
                    caption=message.caption,
                    reply_markup=custom_keyboard,
                    parse_mode=message.html_text and "HTML" or None
                )
            elif message.sticker:
                await self.bot.send_sticker(
                    chat_id=user_id,
                    sticker=message.sticker.file_id,
                    reply_markup=custom_keyboard
                )
            else:
                # Если тип сообщения не поддерживается
                return False

            return True

        except TelegramRetryAfter:
            raise
        except TelegramForbiddenError:
            # Пользователь заблокировал бота — запоминаем, чтобы не слать ему дальше
            logger.debug(f"Пользователь {user_id} заблокировал бота")
            try:
                await db.set_bot_blocked(user_id, True)
            except Exception as e:
                logger.warning(f"Не удалось пометить {user_id} как заблокировавшего бота: {e}")
            raise
        except TelegramBadRequest as e:
            # Другие ошибки Telegram API
            logger.warning(f"Ошибка отправки пользователю {user_id}: {e}")
            return False
        except Exception as e:
            # Неожиданные ошибки
            logger.error(f"Неожиданная ошибка при отправке пользователю {user_id}: {e}")
            return False
