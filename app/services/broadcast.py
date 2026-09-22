"""
Рассылка: фоновая задача с ровным темпом, курсором по users.id и возобновлением после рестарта.

Telegram допускает ~30 сообщений/с суммарно по всем чатам. Отправляем последовательно, темп задаём
до запроса (BROADCAST_RATE_LIMIT_RPS); на 429 ждём весь retry_after — поток один, поэтому пауза
глобальная. Получатели читаются курсором пачками (память постоянная); каждые CHECKPOINT_EVERY
отправок курсор и счётчики пишутся в строку broadcasts. При старте бота незавершённая рассылка
(status=running) продолжается с курсора (resume_pending); при kill -9 до CHECKPOINT_EVERY
получателей могут получить сообщение дважды — при штатном SIGTERM курсор точный.

Контент — JSON исходного сообщения админа (Message.model_dump_json), отправка через send_copy.
Текст/подпись подменяются на html_text без entities: CustomEmojiMiddleware не трогает текст
с явными entities, а так эмодзи становятся иконками и форматирование сохраняется.

ProgressReporter — общий для долгих операций (рассылка, проверка живых) троттлинг правок прогресса.
"""
import asyncio
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, Literal, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import InlineKeyboardMarkup, Message
from loguru import logger

from app.config import settings
from app.database import db
from app.keyboards import AdminKeyboards
from app.services.admins import notify_admins
from app.services.liveness import liveness

BATCH_SIZE = 500            # id получателей на один запрос к БД
CHECKPOINT_EVERY = 50       # отправок между записями курсора в БД
PROGRESS_EVERY_SECONDS = 5  # не чаще — колбэк прогресса (он редактирует сообщение админа)
MAX_RETRIES = 3             # попыток отправки одному получателю всего (как в liveness), не повторов

Verdict = Literal["sent", "blocked", "failed"]


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


@dataclass
class BroadcastProgress:
    broadcast_id: int
    total: int
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    status: str = "running"  # после завершения: done / stopped / failed; running — прервана рестартом
    started_at: float = field(default_factory=time.monotonic)
    finished_at: Optional[float] = None

    def count(self, verdict: Verdict) -> None:
        if verdict == "sent":
            self.sent += 1
        elif verdict == "blocked":
            self.blocked += 1
        elif verdict == "failed":
            self.failed += 1
        else:
            raise ValueError(f"Неизвестный вердикт отправки: {verdict!r}")

    @property
    def processed(self) -> int:
        return self.sent + self.failed + self.blocked

    @property
    def percent(self) -> int:
        return min(100, self.processed * 100 // self.total) if self.total else 100

    @property
    def elapsed(self) -> timedelta:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return timedelta(seconds=int(end - self.started_at))


ProgressCallback = Callable[[BroadcastProgress], Awaitable[None]]


def build_send_method(message: Message, chat_id: int, keyboard: Optional[InlineKeyboardMarkup]) -> TelegramMethod:
    """Send* по типу сообщения. Текст/подпись — как HTML без entities, чтобы сработали иконки.

    TypeError от send_copy (тип не поддерживается) не ловим: он одинаков для всех получателей
    и должен уронить рассылку целиком, а не дать 150 000 «failed».
    """
    method = message.send_copy(chat_id=chat_id, reply_markup=keyboard)
    if isinstance(method, SendMessage):
        return method.model_copy(update={"text": message.html_text, "entities": None, "parse_mode": "HTML"})
    if getattr(method, "caption", None) is not None:
        return method.model_copy(update={"caption": message.html_text, "caption_entities": None, "parse_mode": "HTML"})
    return method


# Ссылки на наблюдателей возобновлённых рассылок, чтобы задачи не собрал GC
_watchers: set[asyncio.Task] = set()


class BroadcastService:
    """Одна рассылка за раз (в рамках процесса); синглтон `broadcast`, configure(bot) в main.py.

    Зеркалит `LivenessService`: правки жизненного цикла (start/stop/wait) вносить в оба.
    """

    def __init__(self, bot: Optional[Bot] = None):
        self.bot = bot
        self._task: Optional[asyncio.Task] = None
        self.progress: Optional[BroadcastProgress] = None   # текущая рассылка
        self.last_result: Optional[BroadcastProgress] = None
        self._stop_requested = False   # stop() из админки → stopped; отмена без него (shutdown) → running
        self._error_kinds: Counter = Counter()  # что именно ломалось в текущей рассылке

    def configure(self, bot: Bot) -> None:
        self.bot = bot

    def _task_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def is_running(self) -> bool:
        """Идёт ли рассылка — включая вызов run() напрямую, без start()"""
        return self._task_running() or self.progress is not None

    def start(self, broadcast_id: int, progress_callback: Optional[ProgressCallback] = None) -> Optional[asyncio.Task]:
        """Запустить рассылку в фоне. None — если идёт рассылка или проверка живых (общий лимит Telegram)."""
        if self.is_running() or liveness.is_running():
            return None
        self._task = asyncio.create_task(self.run(broadcast_id, progress_callback), name=f"broadcast-{broadcast_id}")
        return self._task

    def stop(self) -> bool:
        """Остановить из админки: статус stopped (финальный). True — если было что останавливать."""
        if not self._task_running():
            return False
        self._stop_requested = True
        if not self._task.cancelling():  # повторный cancel() прилетел бы в await внутри finally
            self._task.cancel()
        return True

    def stop_for_shutdown(self) -> bool:
        """Прервать на выключении бота: статус остаётся running, рассылка возобновится после рестарта."""
        if not self._task_running():
            return False
        if not self._task.cancelling():
            self._task.cancel()
        return True

    async def wait(self, timeout: Optional[float] = None) -> None:
        """Дождаться завершения (в т.ч. после stop()). asyncio.wait — не глушит CancelledError вызывающего."""
        if self._task is None:
            return
        await asyncio.wait({self._task}, timeout=timeout)
        self._log_outcome(self._task)

    @staticmethod
    def _log_outcome(task: asyncio.Task) -> None:
        """Забрать исключение задачи, чтобы оно не потерялось и не всплыло в GC"""
        if not task.done():
            logger.warning("📤 Broadcast: рассылка не завершилась за отведённое время")
            return
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.opt(exception=exc).error("❌ Broadcast crashed")

    async def resume_pending(self) -> None:
        """При старте бота: продолжить рассылку, прерванную рестартом. Итог — всем админам."""
        row = await db.get_running_broadcast()
        if row is None:
            return
        task = self.start(row.id)
        if task is None:
            logger.warning(f"📤 Broadcast #{row.id} не возобновлена: занято — останется running до следующего рестарта")
            return
        logger.info(f"📤 Broadcast #{row.id} resumed at {row.sent + row.failed + row.blocked}/{row.total}")

        async def watch() -> None:
            await asyncio.wait({task})
            self._log_outcome(task)
            result = self.last_result
            if result is None or result.broadcast_id != row.id or result.status == "running":
                return  # чужой итог или снова прервана рестартом — итог придёт после следующего
            await notify_admins(self.bot, format_broadcast_result(result))

        watcher = asyncio.create_task(watch(), name=f"broadcast-{row.id}-watch")
        _watchers.add(watcher)
        watcher.add_done_callback(_watchers.discard)

    async def run(self, broadcast_id: int, progress_callback: Optional[ProgressCallback] = None) -> BroadcastProgress:
        """Одна рассылка от курсора до конца. При отмене дописывает курсор; статус — см. except."""
        if self.bot is None:
            raise RuntimeError("BroadcastService не сконфигурирован (bot=None)")
        # Сброс до первого await: stop() в окне get_broadcast() не должен оставить итог прошлой рассылки
        self.last_result = None  # чтобы наблюдатель не показал итог прошлой рассылки
        self._stop_requested = False
        self._error_kinds = Counter()
        row = await db.get_broadcast(broadcast_id)
        if row is None or row.status != "running":
            raise RuntimeError(f"Рассылка #{broadcast_id} не найдена или уже завершена")
        progress = BroadcastProgress(broadcast_id, total=row.total, sent=row.sent, failed=row.failed, blocked=row.blocked)
        self.progress = progress
        delay = 1 / max(settings.broadcast_rate_limit_rps, 1)
        next_at = time.monotonic()
        after_id = row.last_user_id
        last_report = 0.0  # первый прогресс-колбэк — сразу
        since_checkpoint = 0
        logger.info(f"📤 Broadcast #{broadcast_id} started at {progress.processed}/{progress.total}")

        try:
            # Восстановление контента внутри try: невалидный JSON должен закончиться status=failed,
            # иначе строка останется running и resume_pending() будет поднимать её на каждом рестарте
            message = Message.model_validate_json(row.content)
            keyboard = None
            if row.button_text and row.button_url:
                keyboard = AdminKeyboards.create_custom_button(row.button_text, row.button_url)
            while True:
                ids = await db.get_alive_user_ids(after_id, BATCH_SIZE)
                if not ids:
                    break
                for uid in ids:
                    # Темп задаём до запроса: сеть может отвечать сколь угодно долго,
                    # но частота запросов остаётся ≈ broadcast_rate_limit_rps
                    await asyncio.sleep(max(0.0, next_at - time.monotonic()))
                    next_at = max(next_at, time.monotonic()) + delay

                    progress.count(await self._send(uid, message, keyboard))
                    after_id = uid
                    since_checkpoint += 1

                    if since_checkpoint >= CHECKPOINT_EVERY:
                        await self._checkpoint(progress, after_id)
                        since_checkpoint = 0
                    if progress_callback and time.monotonic() - last_report >= PROGRESS_EVERY_SECONDS:
                        last_report = time.monotonic()
                        try:
                            await progress_callback(progress)
                        except Exception as e:
                            logger.debug(f"broadcast progress callback failed: {e}")
            progress.status = "done"
        except asyncio.CancelledError:
            # stop() из админки → stopped (финал); отмена на shutdown → running, чтобы возобновиться после рестарта
            progress.status = "stopped" if self._stop_requested else "running"
            logger.info(f"📤 Broadcast #{broadcast_id} cancelled at {progress.processed}/{progress.total} → {progress.status}")
            raise
        except Exception as e:
            progress.status = "failed"
            logger.exception(f"❌ Broadcast #{broadcast_id} failed at {progress.processed}/{progress.total}: {e}")
            raise
        finally:
            progress.finished_at = time.monotonic()
            try:
                try:
                    await self._checkpoint(progress, after_id, status=progress.status)
                except Exception as e:
                    logger.exception(f"❌ Не удалось записать итог рассылки #{broadcast_id}: {e}")
            finally:
                # Второй cancel() (двойной «Стоп», asyncio.run на выходе) прилетает в await выше —
                # сброс всё равно обязателен, иначе is_running() останется True навсегда
                self.last_result = progress
                self.progress = None
                logger.info(
                    f"📤 Broadcast #{broadcast_id} {progress.status}: sent={progress.sent} failed={progress.failed} "
                    f"blocked={progress.blocked} of {progress.total}{self._errors_summary()}"
                )
        return progress

    async def _checkpoint(self, progress: BroadcastProgress, after_id: int, status: Optional[str] = None) -> None:
        """Курсор и счётчики в БД; status='running' на shutdown не проставляет finished_at"""
        await db.update_broadcast(
            progress.broadcast_id, last_user_id=after_id, sent=progress.sent, failed=progress.failed,
            blocked=progress.blocked, status=status,
        )

    def _errors_summary(self) -> str:
        """Топ-5 видов ошибок — чтобы не разбирать логи по одному получателю"""
        if not self._error_kinds:
            return ""
        return f" kinds={dict(self._error_kinds.most_common(5))}"

    async def _send(self, user_id: int, message: Message, keyboard: Optional[InlineKeyboardMarkup]) -> Verdict:
        """Одному получателю: 'sent' | 'blocked' | 'failed'. На 429 ждём весь retry_after."""
        method = build_send_method(message, user_id, keyboard)
        for _ in range(MAX_RETRIES):
            try:
                await self.bot(method)
                return "sent"
            except TelegramRetryAfter as e:
                logger.warning(f"📤 broadcast: флуд-лимит Telegram, ждём {e.retry_after} с")
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                await self._mark_blocked(user_id)
                return "blocked"
            except TelegramBadRequest as e:
                text = str(e).lower()
                if "chat not found" in text or "user is deactivated" in text:
                    await self._mark_blocked(user_id)
                    return "blocked"
                self._error_kinds[f"BadRequest:{e.message[:60]}"] += 1
                logger.debug(f"📤 broadcast: ошибка отправки {user_id}: {e}")
                return "failed"
            except Exception as e:
                self._error_kinds[type(e).__name__] += 1
                logger.debug(f"📤 broadcast: ошибка отправки {user_id}: {e}")
                return "failed"
        self._error_kinds["RetryAfter:exhausted"] += 1
        logger.debug(f"📤 broadcast: {user_id} пропущен — {MAX_RETRIES} флуд-лимита подряд")
        return "failed"

    async def _mark_blocked(self, user_id: int) -> None:
        """Заблокировал бота или удалил аккаунт — больше не слать"""
        try:
            await db.set_bot_blocked(user_id, True)
        except Exception as e:
            logger.warning(f"Не удалось пометить {user_id} как заблокировавшего бота: {e}")

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
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await self._send_once(user_id, message, custom_keyboard)
            except TelegramRetryAfter as e:
                # Flood-wait: Telegram просит подождать. Ждём и повторяем,
                # иначе получатель молча выпал бы из рассылки.
                if attempt >= MAX_RETRIES:
                    logger.warning(
                        f"Пользователь {user_id}: flood-wait {e.retry_after}s, "
                        f"попытки исчерпаны ({MAX_RETRIES})"
                    )
                    return False
                logger.warning(
                    f"Пользователь {user_id}: flood-wait {e.retry_after}s, "
                    f"повтор {attempt + 1}/{MAX_RETRIES}"
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


STATUS_TITLES = {
    "done": "✅ <b>Рассылка завершена</b>",
    "stopped": "⏹ <b>Рассылка остановлена</b>",
    "failed": "❌ <b>Рассылка упала</b>",
}
STATUS_LABELS = {"running": "идёт", "done": "завершена", "stopped": "остановлена", "failed": "упала"}


def format_broadcast_progress(progress: BroadcastProgress) -> str:
    return (
        "📤 <b>Рассылка…</b>\n\n"
        f"Отправлено: <b>{progress.processed}</b> из {progress.total} ({progress.percent}%)\n"
        f"✅ доставлено: {progress.sent} · ❌ ошибок: {progress.failed} · 🚫 заблокировали: {progress.blocked}\n"
        f"⏱ {progress.elapsed}"
    )


def format_broadcast_result(result: BroadcastProgress) -> str:
    """Итог рассылки для админа (сообщение прогресса или уведомление после возобновления)"""
    success = int(result.sent * 100 / result.total) if result.total else 0
    lines = [STATUS_TITLES.get(result.status, STATUS_TITLES["failed"]), ""]
    if result.status == "stopped":
        lines.append(f"Остановлена на <b>{result.processed}</b> из {result.total}")
    lines += [
        f"👥 Получателей: <b>{result.total}</b>",
        f"✅ Доставлено: <b>{result.sent}</b>",
        f"❌ Ошибок: <b>{result.failed}</b>",
        f"🚫 Заблокировали бота: <b>{result.blocked}</b>",
        f"📈 Успешность: <b>{success}%</b>",
        f"⏱ Длительность: {result.elapsed}",
    ]
    return "\n".join(lines)


# Глобальный экземпляр: configure(bot) в main.py и в хендлере подтверждения.
# Не экспортировать из app/services/__init__.py — атрибут app.services.broadcast должен остаться модулем
broadcast = BroadcastService()
