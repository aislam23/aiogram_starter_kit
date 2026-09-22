"""
Админские хендлеры
"""
import asyncio
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from loguru import logger

from app.config import settings
from app.database import db
from app.filters import IsAdmin
from app.keyboards import AdminKeyboards
from app.middlewares.custom_emoji import custom_emoji_status
from app.services.broadcast import (
    STATUS_LABELS,
    BroadcastProgress,
    ProgressReporter,
    broadcast,
    format_broadcast_progress,
    format_broadcast_result,
)
from app.services.liveness import liveness
from app.states import AdminStates

router = Router()

# Ссылки на наблюдателей за рассылкой, чтобы задачи не собрал GC
_watchers: set[asyncio.Task] = set()


def fmt_local(dt: datetime, fmt: str) -> str:
    """Время в часовом поясе бота (settings.timezone), а не в UTC из БД"""
    return dt.astimezone(ZoneInfo(settings.timezone)).strftime(fmt)


async def _show_broadcast_running(callback: CallbackQuery) -> None:
    """Экран текущей рассылки"""
    if broadcast.progress is not None:
        text = format_broadcast_progress(broadcast.progress)
    else:
        text = "📤 <b>Рассылка…</b>\n\nЗапускаю…"
    await ProgressReporter(callback.message, min_interval=0).update(text, AdminKeyboards.broadcast_running())


async def broadcast_status_line() -> str:
    """Строка о рассылке для панели /admin"""
    progress = broadcast.progress
    if progress is not None:
        return f"📤 Рассылка: идёт <b>{progress.processed} / {progress.total}</b> ({progress.percent}%)"
    last = await db.get_last_broadcast()
    if last is None:
        return "📤 Рассылок ещё не было"
    when = fmt_local(last.finished_at or last.created_at, "%d.%m %H:%M")
    return f"📤 Последняя рассылка: <b>{when}</b> — {STATUS_LABELS.get(last.status, last.status)}, {last.sent} / {last.total}"


# Признак админа приходит из UserMiddleware как аргумент хендлера `is_admin: bool`
# (учитывает ADMIN_USER_IDS и админов, распознанных по ADMIN_USERNAMES).


@router.message(Command("cancel"), IsAdmin())
async def cancel_any_state(message: Message, state: FSMContext):
    """Отмена любого состояния админа.

    Объявлен раньше хендлеров состояний, иначе /cancel во время рассылки
    будет воспринят как текст рассылки. IsAdmin() нужен, чтобы не перехватывать
    /cancel у обычных пользователей — их роутеры получат команду сами.
    """
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        # ReplyKeyboardRemove — чтобы reply-клавиатура (например, выбор пользователя) не осталась висеть
        await message.answer("❌ Операция отменена", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("ℹ️ Нет активных операций для отмены")


@router.message(Command("admin"))
async def admin_command(message: Message, bot: Bot, is_admin: bool = False):
    """Обработчик команды /admin"""
    if not is_admin:
        await message.answer("❌ У вас нет прав администратора")
        return

    await message.answer(text=await admin_panel_text(), reply_markup=AdminKeyboards.main_admin_menu())


async def admin_panel_text() -> str:
    """Текст главного экрана админки со статистикой (используется и для возврата «Назад»)"""
    icons_label, icons_note = custom_emoji_status.describe()
    broadcast_line = await broadcast_status_line()
    stats = await db.get_bot_stats()
    if not stats:
        stats = await db.update_bot_stats()

    total_users = await db.get_users_count()
    alive_users = await db.get_alive_users_count()
    blocked_users = await db.get_blocked_users_count()
    last_restart = fmt_local(stats.last_restart, "%d.%m.%Y %H:%M:%S")

    return f"""
🔧 <b>Админская панель</b>

📊 <b>Статистика бота:</b>
👥 Всего пользователей: <b>{total_users}</b>
✅ Живых: <b>{alive_users}</b>
🚫 Заблокировали бота: <b>{blocked_users}</b>
🟢 Статус: <b>{stats.status}</b>
🕐 Последний запуск: <b>{last_restart}</b>
⚙️ Иконки: <b>{icons_label}</b>{icons_note}
{broadcast_line}

Выберите действие:
"""


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    """Начало создания рассылки"""
    if not is_admin:
        await callback.answer("❌ У вас нет прав администратора")
        return

    if broadcast.is_running():
        await _show_broadcast_running(callback)
        await callback.answer("Рассылка уже идёт")
        return

    await state.set_state(AdminStates.broadcast_message)

    await callback.message.edit_text(
        "📤 <b>Создание рассылки</b>\n\n"
        "Отправьте сообщение любого типа (текст, фото, видео, документ и т.д.), "
        "которое хотите разослать всем пользователям бота.\n\n"
        "Для отмены введите /cancel"
    )

    await callback.answer()


@router.message(StateFilter(AdminStates.broadcast_message))
async def receive_broadcast_message(message: Message, state: FSMContext, is_admin: bool = False):
    """Получение сообщения для рассылки"""
    if not is_admin:
        await state.clear()
        return

    # Строка JSON, не объект: RedisStorage хранит данные через json.dumps
    await state.update_data(broadcast_message=message.model_dump_json())

    # Получаем количество пользователей для рассылки
    users_count = await db.get_alive_users_count()

    await message.answer(
        f"✅ <b>Сообщение получено!</b>\n\n"
        f"👥 Количество получателей: <b>{users_count}</b>\n\n"
        f"Хотите добавить кнопку к сообщению?",
        reply_markup=AdminKeyboards.broadcast_add_button()
    )


@router.callback_query(F.data == "broadcast_add_button", StateFilter(AdminStates.broadcast_message))
async def add_button_to_broadcast(callback: CallbackQuery, state: FSMContext):
    """Добавление кнопки к рассылке"""
    await state.set_state(AdminStates.broadcast_button)

    await callback.message.edit_text(
        "🔗 <b>Добавление кнопки</b>\n\n"
        "Отправьте кнопку в формате:\n"
        "<code>Текст кнопки | https://example.com</code>\n\n"
        "Пример:\n"
        "<code>Наш сайт | https://example.com</code>\n\n"
        "Для отмены введите /cancel"
    )

    await callback.answer()


@router.message(StateFilter(AdminStates.broadcast_button))
async def receive_broadcast_button(message: Message, state: FSMContext, is_admin: bool = False):
    """Получение кнопки для рассылки"""
    if not is_admin:
        await state.clear()
        return

    # Парсим кнопку
    button_pattern = r"^(.+?)\s*\|\s*(https?://.+)$"
    match = re.match(button_pattern, message.text.strip())

    if not match:
        await message.answer(
            "❌ <b>Неверный формат кнопки!</b>\n\n"
            "Используйте формат:\n"
            "<code>Текст кнопки | https://example.com</code>\n\n"
            "Попробуйте еще раз или введите /cancel для отмены"
        )
        return

    button_text = match.group(1).strip()
    button_url = match.group(2).strip()

    # Сохраняем данные кнопки
    await state.update_data(
        button_text=button_text,
        button_url=button_url
    )

    # Создаем превью кнопки
    preview_keyboard = AdminKeyboards.create_custom_button(button_text, button_url)

    await message.answer(
        f"✅ <b>Кнопка создана!</b>\n\n"
        f"📝 Текст: <b>{button_text}</b>\n"
        f"🔗 Ссылка: <code>{button_url}</code>\n\n"
        f"Превью кнопки:",
        reply_markup=preview_keyboard
    )

    # Переходим к подтверждению
    users_count = await db.get_alive_users_count()

    await message.answer(
        f"📤 <b>Подтверждение рассылки</b>\n\n"
        f"👥 Получателей: <b>{users_count}</b>\n"
        f"🔗 С кнопкой: <b>Да</b>\n\n"
        f"Отправить рассылку?",
        reply_markup=AdminKeyboards.broadcast_confirm(users_count)
    )


@router.callback_query(F.data == "broadcast_no_button", StateFilter(AdminStates.broadcast_message))
async def broadcast_without_button(callback: CallbackQuery, state: FSMContext):
    """Рассылка без кнопки"""
    users_count = await db.get_alive_users_count()

    await callback.message.edit_text(
        f"📤 <b>Подтверждение рассылки</b>\n\n"
        f"👥 Получателей: <b>{users_count}</b>\n"
        f"🔗 С кнопкой: <b>Нет</b>\n\n"
        f"Отправить рассылку?",
        reply_markup=AdminKeyboards.broadcast_confirm(users_count)
    )

    await callback.answer()


@router.callback_query(F.data == "broadcast_confirm_yes")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot, is_admin: bool = False):
    """Подтверждение: запись в БД и запуск рассылки в фоне; прогресс и итог — в этом же сообщении"""
    if not is_admin:
        await callback.answer("❌ У вас нет прав администратора")
        return

    data = await state.get_data()
    content = data.get("broadcast_message")
    if not content:
        await callback.message.edit_text("❌ Ошибка: сообщение для рассылки не найдено")
        await state.clear()
        return

    if broadcast.is_running():
        await state.clear()
        await _show_broadcast_running(callback)
        await callback.answer("Рассылка уже идёт", show_alert=True)
        return
    if liveness.is_running():
        await state.clear()
        await callback.answer("Идёт проверка живых — дождитесь её окончания", show_alert=True)
        return

    # Отвечаем на callback сразу: рассылка идёт долго, а callback query протухает через несколько секунд.
    # State чистим сразу же — хендлер больше не ждёт конца рассылки. Оба вызова — ДО записи строки в БД:
    # они могут упасть (query too old, Redis), а строка running без задачи — это «зомби»,
    # которую resume_pending() поднимет после рестарта
    await callback.answer()
    await state.clear()

    broadcast_id = await db.create_broadcast(
        created_by=callback.from_user.id, content=content,
        button_text=data.get("button_text"), button_url=data.get("button_url"),
        total=await db.get_alive_users_count(),
    )

    # Между вставкой строки и start() — только sync configure() и update(), который глотает исключения
    broadcast.configure(bot)
    reporter = ProgressReporter(callback.message)

    async def on_progress(progress: BroadcastProgress) -> None:
        await reporter.update(format_broadcast_progress(progress), AdminKeyboards.broadcast_running())

    # Сначала экран «Запускаю…», потом старт: иначе первый прогресс-колбэк
    # может обогнать эту правку и «Запускаю…» перезатрёт прогресс
    await reporter.update("📤 <b>Рассылка…</b>\n\nЗапускаю…", AdminKeyboards.broadcast_running())

    task = broadcast.start(broadcast_id, on_progress)
    if task is None:
        # Проиграли гонку другому админу или планировщику liveness между проверкой выше и стартом
        await db.update_broadcast(broadcast_id, last_user_id=0, sent=0, failed=0, blocked=0, status="failed")
        reason = "идёт проверка живых" if liveness.is_running() else "рассылка уже идёт"
        await reporter.finish(f"⚠️ Рассылка не запущена: {reason}", AdminKeyboards.broadcast_done())
        return

    async def watch() -> None:
        await asyncio.wait({task})
        if task.cancelled():
            result = broadcast.last_result  # run() дописывает итог в finally перед raise
            # чужой итог (гонка с другой рассылкой) или running — бот выключается, итог после рестарта
            if result is not None and result.broadcast_id == broadcast_id and result.status != "running":
                await reporter.finish(format_broadcast_result(result), AdminKeyboards.broadcast_done())
        elif (exc := task.exception()) is not None:
            logger.opt(exception=exc).error("❌ Broadcast crashed")
            await reporter.finish("❌ Рассылка упала, подробности в логах", AdminKeyboards.broadcast_done())
        else:
            await reporter.finish(format_broadcast_result(task.result()), AdminKeyboards.broadcast_done())

    watcher = asyncio.create_task(watch())
    _watchers.add(watcher)
    watcher.add_done_callback(_watchers.discard)


@router.callback_query(F.data == "broadcast:stop", IsAdmin())
async def broadcast_stop(callback: CallbackQuery) -> None:
    """Остановить текущую рассылку; итог допишет наблюдатель из confirm_broadcast"""
    if broadcast.stop():
        await callback.answer("Останавливаю…")
    else:
        await callback.answer("Рассылка не идёт")


@router.callback_query(F.data == "broadcast:refresh", IsAdmin())
async def broadcast_refresh(callback: CallbackQuery) -> None:
    """Обновить экран рассылки вручную"""
    if broadcast.is_running():
        await _show_broadcast_running(callback)
        await callback.answer()
        return
    result = broadcast.last_result
    if result is not None and result.status != "running":
        await ProgressReporter(callback.message, min_interval=0).update(
            format_broadcast_result(result), AdminKeyboards.broadcast_done()
        )
    await callback.answer("Рассылка не идёт")


@router.callback_query(F.data == "broadcast:back", IsAdmin())
async def broadcast_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text(await admin_panel_text(), reply_markup=AdminKeyboards.main_admin_menu())
    await callback.answer()


@router.callback_query(F.data == "broadcast_confirm_no")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена")
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания рассылки"""
    await state.clear()
    await callback.message.edit_text("❌ Создание рассылки отменено")
    await callback.answer()
