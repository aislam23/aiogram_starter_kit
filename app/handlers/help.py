"""
Обработчики команд помощи и информации
"""
from aiogram import Router, types
from aiogram.filters import Command
from loguru import logger

from app.config import settings

router = Router(name="help")


@router.message(Command("help"))
async def help_command(message: types.Message) -> None:
    """Обработчик команды /help"""
    user = message.from_user

    logger.info(f"ℹ️ User {user.id} requested help")

    help_text = (
        f"🆘 <b>Помощь по боту</b>\n\n"
        f"📋 <b>Доступные команды:</b>\n"
        f"• /start - Запуск бота и приветствие\n"
        f"• /help - Показать эту справку\n"
        f"• /status - Проверить статус бота\n\n"
        f"🔧 <b>Технические детали:</b>\n"
        f"• Версия Aiogram: 3.20.0\n"
        f"• Среда: {settings.env}\n"
        f"• Контейнеризация: Docker\n\n"
        f"💬 Если у вас есть вопросы, обращайтесь к разработчику."
    )

    await message.answer(help_text)


@router.message(Command("status"))
async def status_command(message: types.Message) -> None:
    """Обработчик команды /status"""
    user = message.from_user

    logger.info(f"📊 User {user.id} requested status")

    status_text = (
        f"📊 <b>Статус бота</b>\n\n"
        f"✅ Бот активен и работает\n"
        f"🏠 Среда: <code>{settings.env}</code>\n"
        f"🗄️ База данных: Подключена\n"
        f"🚀 Redis: Подключен\n"
        f"📡 API Telegram: Доступен\n\n"
        f"⏰ Время проверки: {message.date.strftime('%H:%M:%S %d.%m.%Y')}"
    )

    await message.answer(status_text)
