"""
Обработчик команды /start
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from app.database import db

router = Router()


@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Сохраняем пользователя в базу данных
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Приветственное сообщение
    welcome_text = f"""
👋 Привет, {user.first_name or 'пользователь'}!

Добро пожаловать в наш бот! 

Для получения помощи используйте команду /help
"""
    
    await message.answer(welcome_text)
