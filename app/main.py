"""
Главный файл бота
"""
import asyncio
import sys

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from loguru import logger

from app.config import settings
from app.database import db
from app.handlers import setup_routers
from app.middlewares import setup_middlewares
from app.utils import register_secret, setup_logging


async def check_local_api_available() -> bool:
    """Проверка доступности Local Bot API Server"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                settings.local_api_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                # Local API возвращает 404 на root, но соединение работает
                return response.status in (200, 404)
    except Exception:
        return False


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""

    # Настройка session в зависимости от режима API
    session = None
    if settings.use_local_api:
        logger.info("🔧 Initializing Local Bot API mode...")
        logger.info(f"📡 API URL: {settings.local_api_url}")

        if await check_local_api_available():
            session = AiohttpSession(
                api=TelegramAPIServer.from_base(settings.local_api_url, is_local=True)
            )
            logger.info("✅ Local Bot API connected")
            logger.info(f"📁 File upload limit: {settings.file_upload_limit_mb} MB")
        else:
            logger.warning("⚠️ Local Bot API not available, using Public API")
    else:
        logger.info("🌍 Using Public Bot API")
        logger.info(f"📁 File upload limit: {settings.file_upload_limit_mb} MB")

    # Создаем бота
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session
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
    logger.info(f"🌐 API Mode: {settings.api_mode_name}")


async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке бота"""
    logger.info("🛑 Bot is shutting down...")
    await bot.session.close()


async def main() -> None:
    """Главная функция"""

    # Настройка логирования: stdout + JSON-файл, секреты маскируются
    register_secret(settings.bot_token)
    register_secret(settings.postgres_password)
    register_secret(settings.redis_password)
    setup_logging(level=settings.log_level, log_file=settings.log_file)

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
