"""
Админские хендлеры
"""
import re
from datetime import datetime
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.config import settings
from app.database import db
from app.states import AdminStates
from app.keyboards import AdminKeyboards
from app.services import BroadcastService

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return settings.is_admin(user_id)


@router.message(Command("admin"))
async def admin_command(message: Message, bot: Bot):
    """Обработчик команды /admin"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Получаем статистику бота
    stats = await db.get_bot_stats()
    if not stats:
        # Если статистики нет, создаем её
        stats = await db.update_bot_stats()
    
    # Получаем актуальные данные
    total_users = await db.get_users_count()
    active_users = await db.get_active_users_count()
    
    # Форматируем время последнего запуска
    last_restart = stats.last_restart.strftime("%d.%m.%Y %H:%M:%S")
    
    # Формируем сообщение со статистикой
    text = f"""
🔧 <b>Админская панель</b>

📊 <b>Статистика бота:</b>
👥 Всего пользователей: <b>{total_users}</b>
✅ Активных пользователей: <b>{active_users}</b>
🟢 Статус: <b>{stats.status}</b>
🕐 Последний запуск: <b>{last_restart}</b>

Выберите действие:
"""
    
    await message.answer(
        text=text,
        reply_markup=AdminKeyboards.main_admin_menu()
    )


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начало создания рассылки"""
    if not is_admin(callback.from_user.id):
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
async def receive_broadcast_message(message: Message, state: FSMContext):
    """Получение сообщения для рассылки"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    # Сохраняем сообщение в состояние
    await state.update_data(broadcast_message=message)
    
    # Получаем количество пользователей для рассылки
    users_count = await db.get_active_users_count()
    
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
async def receive_broadcast_button(message: Message, state: FSMContext):
    """Получение кнопки для рассылки"""
    if not is_admin(message.from_user.id):
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
    data = await state.get_data()
    users_count = await db.get_active_users_count()
    
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
    users_count = await db.get_active_users_count()
    
    await callback.message.edit_text(
        f"📤 <b>Подтверждение рассылки</b>\n\n"
        f"👥 Получателей: <b>{users_count}</b>\n"
        f"🔗 С кнопкой: <b>Нет</b>\n\n"
        f"Отправить рассылку?",
        reply_markup=AdminKeyboards.broadcast_confirm(users_count)
    )
    
    await callback.answer()


@router.callback_query(F.data == "broadcast_confirm_yes")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение и запуск рассылки"""
    if not is_admin(callback.from_user.id):
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
    
    # Функция для обновления прогресса
    async def update_progress(stats: dict):
        progress_percent = int((stats["sent"] + stats["failed"] + stats["blocked"]) / stats["total"] * 100)
        
        try:
            await progress_message.edit_text(
                f"📤 <b>Рассылка в процессе...</b>\n\n"
                f"📊 Прогресс: <b>{progress_percent}%</b>\n"
                f"✅ Отправлено: <b>{stats['sent']}</b>\n"
                f"❌ Ошибок: <b>{stats['failed']}</b>\n"
                f"🚫 Заблокировано: <b>{stats['blocked']}</b>"
            )
        except Exception:
            # Игнорируем ошибки обновления прогресса
            pass
    
    # Запускаем рассылку
    try:
        final_stats = await broadcast_service.send_broadcast(
            message=broadcast_message,
            custom_keyboard=custom_keyboard,
            progress_callback=update_progress
        )
        
        # Финальная статистика
        success_rate = int(final_stats["sent"] / final_stats["total"] * 100) if final_stats["total"] > 0 else 0
        
        await progress_message.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📊 <b>Итоговая статистика:</b>\n"
            f"👥 Всего получателей: <b>{final_stats['total']}</b>\n"
            f"✅ Успешно доставлено: <b>{final_stats['sent']}</b>\n"
            f"❌ Ошибок доставки: <b>{final_stats['failed']}</b>\n"
            f"🚫 Заблокировали бота: <b>{final_stats['blocked']}</b>\n"
            f"📈 Успешность: <b>{success_rate}%</b>"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        await progress_message.edit_text(
            f"❌ <b>Ошибка при рассылке!</b>\n\n"
            f"Описание: <code>{str(e)}</code>"
        )
    
    await state.clear()
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


@router.message(Command("cancel"))
async def cancel_any_state(message: Message, state: FSMContext):
    """Отмена любого состояния"""
    if not is_admin(message.from_user.id):
        return
    
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Операция отменена")
    else:
        await message.answer("ℹ️ Нет активных операций для отмены") 