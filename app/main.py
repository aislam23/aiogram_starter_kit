"""
Главный файл бота
"""
import asyncio
import sys
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.config import settings
from app.handlers import setup_routers
from app.middlewares import setup_middlewares
from app.database import db


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""
    
    # Создаем бота
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаем хранилище состояний
    try:
        storage = RedisStorage.from_url(settings.redis_url)
        logger.info("✅ Redis storage connected successfully")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # Создаем диспетчер
    dp = Dispatcher(storage=storage)
    
    # Настраиваем middleware
    setup_middlewares(dp)
    
    # Настраиваем роутеры
    setup_routers(dp)
    
    return bot, dp


async def on_startup(bot: Bot) -> None:
    """Действия при запуске бота"""
    # Инициализируем базу данных
    try:
        await db.create_tables()
        await db.update_bot_stats()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        sys.exit(1)
    
    bot_info = await bot.get_me()
    logger.info(f"🚀 Bot @{bot_info.username} started successfully!")
    logger.info(f"🏠 Environment: {settings.env}")


async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке бота"""
    logger.info("🛑 Bot is shutting down...")
    await bot.session.close()


async def main() -> None:
    """Главная функция"""
    
    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True
    )
    
    logger.info("🎯 Starting Aiogram Bot...")
    
    # Создаем бота и диспетчер
    bot, dp = await setup_bot()
    
    # Регистрируем startup и shutdown обработчики
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        # Запускаем polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Application terminated by user")
