"""
Обработчик команды /start
"""
from aiogram import Router, types
from aiogram.filters import CommandStart
from loguru import logger

router = Router(name="start")


@router.message(CommandStart())
async def start_command(message: types.Message) -> None:
    """Обработчик команды /start"""
    user = message.from_user
    
    logger.info(f"👋 User {user.id} (@{user.username}) started the bot")
    
    welcome_text = (
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        f"🤖 Это стартовый шаблон бота на Aiogram v3\n"
        f"🐳 Запущен в Docker контейнере\n\n"
        f"📝 Доступные команды:\n"
        f"• /start - Запуск бота\n"
        f"• /help - Помощь\n"
        f"• /status - Статус бота\n\n"
        f"✨ Готов к разработке!"
    )
    
    await message.answer(welcome_text)
