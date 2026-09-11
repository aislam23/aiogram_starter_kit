"""
Админские хендлеры
"""
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from loguru import logger

from app.database import db
from app.filters import IsAdmin
from app.keyboards import AdminKeyboards
from app.services import BroadcastService, ProgressReporter
from app.states import AdminStates

router = Router()


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
    stats = await db.get_bot_stats()
    if not stats:
        stats = await db.update_bot_stats()

    total_users = await db.get_users_count()
    alive_users = await db.get_alive_users_count()
    blocked_users = await db.get_blocked_users_count()
    last_restart = stats.last_restart.strftime("%d.%m.%Y %H:%M:%S")

    return f"""
🔧 <b>Админская панель</b>

📊 <b>Статистика бота:</b>
👥 Всего пользователей: <b>{total_users}</b>
✅ Живых: <b>{alive_users}</b>
🚫 Заблокировали бота: <b>{blocked_users}</b>
🟢 Статус: <b>{stats.status}</b>
🕐 Последний запуск: <b>{last_restart}</b>

Выберите действие:
"""


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    """Начало создания рассылки"""
    if not is_admin:
        await callback.answer("❌ У вас нет прав администратора")
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

    # Сохраняем сообщение в состояние
    await state.update_data(broadcast_message=message)

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
    """Подтверждение и запуск рассылки"""
    if not is_admin:
        await callback.answer("❌ У вас нет прав администратора")
        return

    data = await state.get_data()
    broadcast_message = data.get("broadcast_message")

    if not broadcast_message:
        await callback.message.edit_text("❌ Ошибка: сообщение для рассылки не найдено")
        await state.clear()
        return

    # Создаем кнопку если есть
    custom_keyboard = None
    if data.get("button_text") and data.get("button_url"):
        custom_keyboard = AdminKeyboards.create_custom_button(
            data["button_text"],
            data["button_url"]
        )

    # Отвечаем на callback сразу: рассылка идёт долго, а callback query
    # протухает через несколько секунд — ответ в конце вызвал бы ошибку
    await callback.answer()

    # Начинаем рассылку
    broadcast_service = BroadcastService(bot)

    # Сообщение о начале рассылки
    progress_message = await callback.message.edit_text(
        "📤 <b>Рассылка запущена...</b>\n\n"
        "📊 Прогресс: <b>0%</b>\n"
        "✅ Отправлено: <b>0</b>\n"
        "❌ Ошибок: <b>0</b>\n"
        "🚫 Заблокировано: <b>0</b>"
    )
    reporter = ProgressReporter(progress_message)

    # Функция для обновления прогресса (репортер сам троттлит и переживает flood-wait)
    async def update_progress(stats: dict):
        progress_percent = int((stats["sent"] + stats["failed"] + stats["blocked"]) / stats["total"] * 100)
        await reporter.update(
            f"📤 <b>Рассылка в процессе...</b>\n\n"
            f"📊 Прогресс: <b>{progress_percent}%</b>\n"
            f"✅ Отправлено: <b>{stats['sent']}</b>\n"
            f"❌ Ошибок: <b>{stats['failed']}</b>\n"
            f"🚫 Заблокировано: <b>{stats['blocked']}</b>"
        )

    # Запускаем рассылку
    try:
        final_stats = await broadcast_service.send_broadcast(
            message=broadcast_message,
            custom_keyboard=custom_keyboard,
            progress_callback=update_progress
        )

        await reporter.finish(format_broadcast_report(final_stats))

    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        await reporter.finish(
            f"❌ <b>Ошибка при рассылке!</b>\n\n"
            f"Описание: <code>{str(e)}</code>"
        )
    finally:
        # Сбрасываем состояние при любом исходе, иначе следующее сообщение
        # админа будет принято за контент новой рассылки
        await state.clear()


def format_broadcast_report(final_stats: dict) -> str:
    """Текст финального отчёта о рассылке"""
    success_rate = int(final_stats["sent"] / final_stats["total"] * 100) if final_stats["total"] > 0 else 0
    return (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 <b>Итоговая статистика:</b>\n"
        f"👥 Всего получателей: <b>{final_stats['total']}</b>\n"
        f"✅ Успешно доставлено: <b>{final_stats['sent']}</b>\n"
        f"❌ Ошибок доставки: <b>{final_stats['failed']}</b>\n"
        f"🚫 Заблокировали бота: <b>{final_stats['blocked']}</b>\n"
        f"📈 Успешность: <b>{success_rate}%</b>"
    )


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
