"""
Сервис рассылки сообщений
"""
import asyncio
from typing import List, Optional, Dict, Any
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from loguru import logger

from app.database import db


class BroadcastService:
    """Сервис для рассылки сообщений"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_broadcast(
        self,
        message: Message,
        custom_keyboard: Optional[InlineKeyboardMarkup] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, int]:
        """
        Отправка рассылки всем пользователям
        
        Args:
            message: Сообщение для рассылки
            custom_keyboard: Кастомная клавиатура
            progress_callback: Функция для отслеживания прогресса
            
        Returns:
            Словарь со статистикой отправки
        """
        users = await db.get_active_users()
        
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
            
        except TelegramForbiddenError:
            # Пользователь заблокировал бота
            logger.debug(f"Пользователь {user_id} заблокировал бота")
            raise
        except TelegramBadRequest as e:
            # Другие ошибки Telegram API
            logger.warning(f"Ошибка отправки пользователю {user_id}: {e}")
            return False
        except Exception as e:
            # Неожиданные ошибки
            logger.error(f"Неожиданная ошибка при отправке пользователю {user_id}: {e}")
            return False 