"""
Проверка живых пользователей из админки: подтверждение → прогон в фоне → итог.

Прогресс и итог редактируются в том же сообщении через ProgressReporter,
чтобы не упереться во flood control на editMessageText.
"""
import asyncio

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from loguru import logger

from app.config import settings
from app.database import db
from app.filters import IsAdmin
from app.keyboards import AdminKeyboards
from app.services.broadcast import ProgressReporter
from app.services.liveness import LivenessProgress, format_progress, format_result, liveness

router = Router(name="admin_liveness")

# Ссылки на наблюдателей за прогоном, чтобы задачи не собрал GC
_watchers: set[asyncio.Task] = set()


async def _show_running(callback: CallbackQuery) -> None:
    """Экран текущего прогона"""
    if liveness.progress is not None:
        text = format_progress(liveness.progress)
    else:
        text = "🩺 <b>Проверка живых…</b>\n\nЗапускаю…"
    await ProgressReporter(callback.message, min_interval=0).update(text, AdminKeyboards.liveness_running())


@router.callback_query(F.data == "admin_liveness", IsAdmin())
async def liveness_menu(callback: CallbackQuery) -> None:
    """Экран подтверждения (или текущий прогон, если он уже идёт)"""
    if liveness.is_running():
        await _show_running(callback)
        await callback.answer("Проверка уже идёт")
        return

    total = await db.count_liveness_users()
    rps = max(settings.liveness_rate_limit_rps, 1)
    minutes = max(1, round(total / rps / 60))
    await callback.message.edit_text(
        "🩺 <b>Проверка живых пользователей</b>\n\n"
        f"Будет проверено ~{total} пользователей через sendChatAction — "
        "пользователи ничего не получат.\n"
        f"Примерное время: ~{minutes} мин. Прогон можно остановить в любой момент.\n\n"
        "⚠️ Во время прогона бот использует ~половину лимита Telegram на отправку — "
        "лучше запускать ночью.\n\n"
        "Запустить?",
        reply_markup=AdminKeyboards.liveness_confirm(),
    )
    await callback.answer()


@router.callback_query(F.data == "liveness:confirm", IsAdmin())
async def liveness_confirm(callback: CallbackQuery, bot: Bot) -> None:
    """Запуск прогона в фоне; прогресс и итог редактируются в этом же сообщении"""
    if liveness.is_running():
        await _show_running(callback)
        await callback.answer("Проверка уже идёт", show_alert=True)
        return

    liveness.configure(bot)
    reporter = ProgressReporter(callback.message)

    async def on_progress(progress: LivenessProgress) -> None:
        await reporter.update(format_progress(progress), AdminKeyboards.liveness_running())

    # Сначала экран «Запускаю…», потом старт: иначе первый прогресс-колбэк
    # может обогнать эту правку и «Запускаю…» перезатрёт прогресс
    await reporter.update("🩺 <b>Проверка живых…</b>\n\nЗапускаю…", AdminKeyboards.liveness_running())

    task = liveness.start("manual", on_progress)
    if task is None:
        # Проиграли гонку другому админу между проверкой выше и стартом
        await callback.answer("Проверка уже идёт", show_alert=True)
        return

    async def watch() -> None:
        await asyncio.wait({task})
        if task.cancelled():
            result = liveness.last_result  # run_check дописывает итог в finally перед raise
            if result is not None:
                await reporter.finish(format_result(result, cancelled=True), AdminKeyboards.liveness_done())
        elif (exc := task.exception()) is not None:
            logger.opt(exception=exc).error("❌ Liveness run crashed")
            await reporter.finish("❌ Проверка упала, подробности в логах", AdminKeyboards.liveness_done())
        else:
            await reporter.finish(format_result(task.result(), cancelled=False), AdminKeyboards.liveness_done())

    watcher = asyncio.create_task(watch())
    _watchers.add(watcher)
    watcher.add_done_callback(_watchers.discard)

    await callback.answer("Запущено")


@router.callback_query(F.data == "liveness:refresh", IsAdmin())
async def liveness_refresh(callback: CallbackQuery) -> None:
    """Обновить экран прогона вручную"""
    if liveness.is_running():
        await _show_running(callback)
        await callback.answer()
        return
    result = liveness.last_result
    if result is not None:
        await ProgressReporter(callback.message, min_interval=0).update(
            format_result(result, cancelled=False), AdminKeyboards.liveness_done()
        )
    await callback.answer("Проверка не идёт")


@router.callback_query(F.data == "liveness:stop", IsAdmin())
async def liveness_stop(callback: CallbackQuery) -> None:
    """Остановить текущий прогон; итог допишет наблюдатель из liveness_confirm"""
    if liveness.stop():
        await callback.answer("Останавливаю…")
    else:
        await callback.answer("Проверка не идёт")


@router.callback_query(F.data == "liveness:back", IsAdmin())
async def liveness_back(callback: CallbackQuery) -> None:
    from .admin import admin_panel_text

    await callback.message.edit_text(await admin_panel_text(), reply_markup=AdminKeyboards.main_admin_menu())
    await callback.answer()
