"""
Проверка «живых» пользователей: sendChatAction каждому не отключённому пользователю.

403 → заблокировал бота, «chat not found» / «user is deactivated» → аккаунт удалён.
Пользователь ничего не получает («печатает…» видно 1–2 с только в открытом чате).

Зачем, если есть my_chat_member: апдейт мог потеряться (бот лежал, вебхук не дошёл),
а база могла быть собрана до появления обработчика. Прогон сверяет базу с реальностью.
"""
import asyncio
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable, Literal, Optional
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from loguru import logger

from app.config import settings
from app.database import db

BATCH_SIZE = 500                 # пользователей на одну транзакцию записи результатов
PROGRESS_EVERY_SECONDS = 5       # не чаще — колбэк прогресса (он редактирует сообщение админа)
SCHEDULER_TICK_SECONDS = 3600
NIGHT_WINDOW = range(3, 6)       # часы по settings.timezone, когда можно запускать автопрогон
MAX_RETRY_AFTER_SECONDS = 60     # дольше ждать флуд-лимит по одному пользователю не имеет смысла
MAX_RETRIES = 3
MAX_CONSECUTIVE_FLOOD_WAITS = 5  # столько флуд-лимитов подряд — Telegram нас не хочет, прерываем прогон

Verdict = Literal["alive", "blocked", "deleted", "error"]


@dataclass
class LivenessProgress:
    total: int
    checked: int = 0
    alive: int = 0
    blocked: int = 0
    deleted: int = 0
    errors: int = 0
    started_at: float = field(default_factory=time.monotonic)
    finished_at: Optional[float] = None

    @property
    def percent(self) -> int:
        return min(100, int(self.checked * 100 / self.total)) if self.total else 100

    @property
    def elapsed(self) -> timedelta:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return timedelta(seconds=int(end - self.started_at))


ProgressCallback = Callable[[LivenessProgress], Awaitable[None]]


class LivenessService:
    """Один прогон за раз (в рамках процесса); планировщик — раз в LIVENESS_CHECK_INTERVAL_DAYS ночью"""

    def __init__(self):
        self.bot: Optional[Bot] = None
        self._task: Optional[asyncio.Task] = None
        self.progress: Optional[LivenessProgress] = None   # текущий прогон
        self.last_result: Optional[LivenessProgress] = None
        self._error_kinds: Counter = Counter()  # что именно ломалось в текущем прогоне
        self._consecutive_flood_waits = 0

    def configure(self, bot: Bot) -> None:
        self.bot = bot

    def _task_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def is_running(self) -> bool:
        """Идёт ли прогон — включая вызов run_check() напрямую, без start()"""
        return self._task_running() or self.progress is not None

    def start(self, trigger: str, progress_callback: Optional[ProgressCallback] = None) -> Optional[asyncio.Task]:
        """Запустить прогон в фоне. None — если прогон уже идёт."""
        if self.is_running():
            return None
        self._task = asyncio.create_task(self.run_check(trigger, progress_callback), name=f"liveness-{trigger}")
        return self._task

    def stop(self) -> bool:
        """Отменить текущий прогон. True — если было что отменять."""
        if self._task_running():
            self._task.cancel()
            return True
        return False

    async def wait(self, timeout: Optional[float] = None) -> None:
        """Дождаться завершения прогона (в т.ч. после stop()).

        Не глушит CancelledError, адресованный вызывающей стороне: ждём через
        asyncio.wait, а не await self._task.
        """
        if self._task is None:
            return
        await asyncio.wait({self._task}, timeout=timeout)
        self._log_outcome(self._task)

    @staticmethod
    def _log_outcome(task: asyncio.Task) -> None:
        """Забрать исключение задачи, чтобы оно не потерялось и не всплыло в GC"""
        if not task.done():
            logger.warning("🩺 Liveness: прогон не завершился за отведённое время")
            return
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.opt(exception=exc).error("❌ Liveness run crashed")

    async def run_check(
        self, trigger: str, progress_callback: Optional[ProgressCallback] = None
    ) -> LivenessProgress:
        """Один полный прогон. При отмене дописывает текущую пачку и закрывает запись прогона."""
        if self.bot is None:
            raise RuntimeError("LivenessService не сконфигурирован (bot=None)")
        self.last_result = None  # чтобы наблюдатель не показал итог прошлого прогона
        self._error_kinds = Counter()
        self._consecutive_flood_waits = 0
        total = await db.count_liveness_users()
        check_id = await db.create_liveness_check(trigger)
        progress = LivenessProgress(total=total)
        self.progress = progress
        delay = 1 / max(settings.liveness_rate_limit_rps, 1)
        last_report = 0.0  # первый прогресс-колбэк — сразу
        next_at = time.monotonic()
        after_id = 0
        logger.info(f"🩺 Liveness check #{check_id} started ({trigger}), users={total}")

        checked_ids: list[int] = []
        alive_ids: list[int] = []
        blocked_ids: list[int] = []
        incomplete = False  # прогон не доведён до конца → не сдвигает расписание
        aborted = False
        try:
            while True:
                ids = await db.get_liveness_user_ids(after_id, BATCH_SIZE)
                if not ids:
                    break
                checked_ids, alive_ids, blocked_ids = [], [], []
                for uid in ids:
                    # Темп задаём до запроса: сеть может отвечать сколь угодно долго,
                    # но частота запросов остаётся ≈ liveness_rate_limit_rps
                    await asyncio.sleep(max(0.0, next_at - time.monotonic()))
                    next_at = max(next_at, time.monotonic()) + delay

                    verdict = await self._probe(uid)
                    checked_ids.append(uid)
                    if verdict == "alive":
                        alive_ids.append(uid)
                        progress.alive += 1
                    elif verdict == "blocked":
                        blocked_ids.append(uid)
                        progress.blocked += 1
                    elif verdict == "deleted":
                        # Удалённые аккаунты тоже помечаются bot_blocked:
                        # отдельного состояния в БД нет, а писать им одинаково бессмысленно
                        blocked_ids.append(uid)
                        progress.deleted += 1
                    else:
                        progress.errors += 1
                    progress.checked += 1

                    if self._consecutive_flood_waits >= MAX_CONSECUTIVE_FLOOD_WAITS:
                        logger.error(
                            f"🩺 liveness: Telegram держит flood-wait "
                            f"{self._consecutive_flood_waits} раз подряд — прерываю прогон"
                        )
                        incomplete = True
                        aborted = True
                        break

                    if progress_callback and time.monotonic() - last_report >= PROGRESS_EVERY_SECONDS:
                        last_report = time.monotonic()
                        try:
                            await progress_callback(progress)
                        except Exception as e:
                            logger.debug(f"liveness progress callback failed: {e}")
                await db.apply_liveness_results(checked_ids, alive_ids, blocked_ids)
                await db.update_liveness_check(
                    check_id, checked=progress.checked, alive=progress.alive, blocked=progress.blocked,
                    deleted=progress.deleted, errors=progress.errors, finished=False,
                )
                # Пачка уже записана: очищаем, чтобы отмена между пачками не записала её повторно
                checked_ids, alive_ids, blocked_ids = [], [], []
                if aborted:
                    break
                after_id = ids[-1]
        except asyncio.CancelledError:
            # Дописываем частично проверенную пачку и выходим
            incomplete = True
            await db.apply_liveness_results(checked_ids, alive_ids, blocked_ids)
            logger.info(
                f"🩺 Liveness check #{check_id} cancelled at {progress.checked}/{total}"
                f"{self._errors_summary()}"
            )
            raise
        except Exception as e:
            # Упавший прогон тоже неполный — расписание не сдвигаем
            incomplete = True
            logger.exception(f"❌ Liveness check #{check_id} failed at {progress.checked}/{total}: {e}")
            raise
        finally:
            progress.finished_at = time.monotonic()
            try:
                await db.update_liveness_check(
                    check_id, checked=progress.checked, alive=progress.alive, blocked=progress.blocked,
                    deleted=progress.deleted, errors=progress.errors, finished=True, cancelled=incomplete,
                )
            except Exception as e:
                logger.exception(f"❌ Не удалось записать итог прогона #{check_id}: {e}")
            self.last_result = progress
            self.progress = None
        logger.info(
            f"🩺 Liveness check #{check_id} finished: checked={progress.checked} alive={progress.alive} "
            f"blocked={progress.blocked} deleted={progress.deleted} errors={progress.errors}"
            f"{self._errors_summary()}"
        )
        return progress

    def _errors_summary(self) -> str:
        """Топ-5 видов ошибок прогона — чтобы не разбирать логи по одному пользователю"""
        if not self._error_kinds:
            return ""
        return f" kinds={dict(self._error_kinds.most_common(5))}"

    async def _probe(self, user_id: int) -> Verdict:
        """'alive' | 'blocked' | 'deleted' | 'error'"""
        for _ in range(MAX_RETRIES):
            try:
                await self.bot.send_chat_action(user_id, ChatAction.TYPING)
                self._consecutive_flood_waits = 0
                return "alive"
            except TelegramRetryAfter as e:
                self._consecutive_flood_waits += 1
                pause = min(e.retry_after, MAX_RETRY_AFTER_SECONDS)
                logger.warning(f"🩺 liveness: флуд-лимит Telegram, ждём {pause} с (retry_after={e.retry_after})")
                await asyncio.sleep(pause)
            except TelegramForbiddenError as e:
                # «user is deactivated» приходит как Forbidden — это удалённый аккаунт
                self._consecutive_flood_waits = 0
                return "deleted" if "deactivated" in str(e).lower() else "blocked"
            except TelegramBadRequest as e:
                self._consecutive_flood_waits = 0
                text = str(e).lower()
                if "chat not found" in text or "user is deactivated" in text:
                    return "deleted"
                self._error_kinds[f"BadRequest:{str(e)[:40]}"] += 1
                logger.debug(f"🩺 liveness: неожиданный BadRequest для {user_id}: {e}")
                return "error"
            except Exception as e:
                self._consecutive_flood_waits = 0
                self._error_kinds[type(e).__name__] += 1
                logger.debug(f"🩺 liveness: ошибка для {user_id}: {e}")
                return "error"
        self._error_kinds["RetryAfter:exhausted"] += 1
        logger.debug(f"🩺 liveness: {user_id} пропущен — {MAX_RETRIES} флуд-лимита подряд")
        return "error"

    # ---------- планировщик ----------

    async def run_scheduler(self) -> None:
        """Раз в час проверяет, не пора ли ночной автопрогон"""
        logger.info(
            f"🩺 Liveness scheduler started (every {settings.liveness_check_interval_days} d, "
            f"night window {NIGHT_WINDOW.start:02d}:00–{NIGHT_WINDOW.stop - 1:02d}:59 {settings.timezone})"
        )
        while True:
            try:
                await self._maybe_run_scheduled()
            except Exception as e:
                logger.exception(f"❌ Liveness scheduler failed: {e}")
            await asyncio.sleep(SCHEDULER_TICK_SECONDS)

    async def _maybe_run_scheduled(self) -> None:
        if settings.liveness_check_interval_days <= 0 or self.is_running():
            return
        local_hour = datetime.now(ZoneInfo(settings.timezone)).hour
        if local_hour not in NIGHT_WINDOW:
            return
        # Остановленный или упавший прогон расписание не сдвигает
        last = await db.get_last_completed_liveness_check()
        if last is not None:
            age = datetime.now(UTC) - last.finished_at
            if age < timedelta(days=settings.liveness_check_interval_days):
                return
        task = self.start("scheduled")
        if task is None:
            return
        await asyncio.wait({task})  # не raise'ит при отмене прогона
        self._log_outcome(task)
        result = self.last_result
        if result is None:
            return
        await self._notify_admins(result, cancelled=task.cancelled())

    async def _notify_admins(self, result: LivenessProgress, cancelled: bool) -> None:
        """Итог автопрогона — всем админам: из настроек и назначенным через бота"""
        text = format_result(result, cancelled, scheduled=True)
        admin_ids = set(settings.admin_user_ids)
        try:
            admin_ids.update(admin.id for admin in await db.get_admins())
        except Exception as e:
            logger.warning(f"Не удалось получить список админов из базы: {e}")
        for admin_id in sorted(admin_ids):
            try:
                await self.bot.send_message(admin_id, text)
            except Exception as e:
                logger.warning(f"Не удалось отправить итог проверки админу {admin_id}: {e}")


def format_result(result: LivenessProgress, cancelled: bool, scheduled: bool = False) -> str:
    """Итог прогона для админа"""
    title = "🩺 <b>Проверка живых остановлена</b>" if cancelled else "🩺 <b>Проверка живых завершена</b>"
    if scheduled:
        title += " (по расписанию)"
    return (
        f"{title}\n\n"
        f"Проверено: <b>{result.checked}</b> из {result.total}\n"
        f"✅ Живых: <b>{result.alive}</b>\n"
        f"🚫 Заблокировали бота: <b>{result.blocked}</b>\n"
        f"👻 Удалённых аккаунтов: <b>{result.deleted}</b>\n"
        f"⚠️ Ошибок: <b>{result.errors}</b>\n"
        f"⏱ Длительность: {result.elapsed}"
    )


def format_progress(progress: LivenessProgress) -> str:
    return (
        "🩺 <b>Проверка живых…</b>\n\n"
        f"Проверено: <b>{progress.checked}</b> из {progress.total} ({progress.percent}%)\n"
        f"✅ Живых: {progress.alive} · 🚫 заблокировали: {progress.blocked} · "
        f"👻 удалённых: {progress.deleted} · ⚠️ ошибок: {progress.errors}\n"
        f"⏱ {progress.elapsed}"
    )


# Глобальный экземпляр (configure(bot) в main.py и в админском хендлере)
liveness = LivenessService()
