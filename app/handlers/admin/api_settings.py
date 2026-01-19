"""
Хендлеры настроек API
"""
import time
from contextlib import suppress

import aiohttp
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from app.config import settings
from app.keyboards import AdminKeyboards
from app.database import db

router = Router()


async def check_local_api_status() -> dict:
    """Проверка статуса Local Bot API Server"""
    result = {"available": False, "response_time_ms": None, "error": None}

    try:
        start = time.monotonic()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                settings.local_api_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                result["response_time_ms"] = int((time.monotonic() - start) * 1000)
                # Local API возвращает 404 на root, но соединение работает
                result["available"] = response.status in (200, 404)
    except aiohttp.ClientConnectorError:
        result["error"] = "Connection refused"
    except Exception as e:
        result["error"] = str(e)

    return result


@router.callback_query(F.data == "admin_api_settings")
async def api_settings_handler(callback: CallbackQuery):
    """Показать настройки API"""
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return

    mode = "Local Bot API" if settings.use_local_api else "Public Bot API"

    text = f"""
<b>Настройки Bot API</b>

<b>Текущий режим:</b> {mode}

<b>Лимиты файлов:</b>
 Загрузка: <b>{settings.file_upload_limit_mb} MB</b>
 Скачивание: <b>{settings.file_download_limit_mb} MB</b>
"""

    if settings.use_local_api:
        text += f"\n<b>URL:</b> <code>{settings.local_api_url}</code>\n"

    await callback.message.edit_text(
        text=text,
        reply_markup=AdminKeyboards.api_settings_menu(settings.use_local_api)
    )
    await callback.answer()


@router.callback_query(F.data == "api_check_status")
async def check_api_status_handler(callback: CallbackQuery):
    """Проверка статуса Local API Server"""
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return

    await callback.answer("Проверяю...")

    status = await check_local_api_status()

    if status["available"]:
        text = f"""
<b>Local Bot API Server доступен!</b>

URL: <code>{settings.local_api_url}</code>
Время ответа: <b>{status['response_time_ms']} мс</b>
Проверено: <code>{time.strftime('%H:%M:%S')}</code>
"""
    else:
        text = f"""
<b>Local Bot API Server недоступен</b>

URL: <code>{settings.local_api_url}</code>
Ошибка: <code>{status.get('error', 'Unknown')}</code>
Проверено: <code>{time.strftime('%H:%M:%S')}</code>

<b>Решения:</b>
1. Запустите: <code>make dev-local</code>
2. Проверьте TELEGRAM_API_ID/HASH
3. Логи: <code>make api-logs</code>
"""

    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            text=text,
            reply_markup=AdminKeyboards.api_settings_menu(settings.use_local_api)
        )


@router.callback_query(F.data == "api_switch_mode")
async def switch_api_mode_handler(callback: CallbackQuery):
    """Инструкция по переключению режима"""
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return

    new_mode = "Local" if not settings.use_local_api else "Public"
    new_value = "true" if not settings.use_local_api else "false"

    text = f"""
<b>Переключение на {new_mode} Bot API</b>

1. Измените в <code>.env</code>:
<code>USE_LOCAL_API={new_value}</code>

2. Перезапустите бота:
<code>make restart-bot</code>
"""

    if not settings.use_local_api:
        text += """
3. Убедитесь, что указаны:
TELEGRAM_API_ID
TELEGRAM_API_HASH

4. Запустите Local API:
<code>make dev-local</code>
"""

    await callback.message.edit_text(text, reply_markup=AdminKeyboards.api_settings_back())
    await callback.answer()


@router.callback_query(F.data == "api_back")
async def api_back_handler(callback: CallbackQuery):
    """Возврат в главное меню"""
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return

    stats = await db.get_bot_stats()
    if not stats:
        stats = await db.update_bot_stats()

    total_users = await db.get_users_count()
    active_users = await db.get_active_users_count()
    last_restart = stats.last_restart.strftime("%d.%m.%Y %H:%M:%S")

    text = f"""
<b>Админская панель</b>

<b>Статистика бота:</b>
Всего пользователей: <b>{total_users}</b>
Активных: <b>{active_users}</b>
Статус: <b>{stats.status}</b>
Последний запуск: <b>{last_restart}</b>
Режим API: <b>{settings.api_mode_name}</b>
"""

    await callback.message.edit_text(text, reply_markup=AdminKeyboards.main_admin_menu())
    await callback.answer()
