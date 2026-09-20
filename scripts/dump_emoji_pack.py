#!/usr/bin/env python3
"""
Выгрузка custom_emoji_id из эмодзи-пака Telegram.

    just emoji-dump [имя_пака]      # по умолчанию tgiosicons

Печатает по строке на стикер: «<эмодзи>\t<custom_emoji_id>». Токен берётся из настроек
(app/config.py) и не печатается. Работает через публичный Bot API (Local Bot API не используется).
Результат используется для каталога app/ui/icons.py.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot  # noqa: E402
from aiogram.utils.token import TokenValidationError  # noqa: E402

DEFAULT_PACK = "tgiosicons"
NO_TOKEN_HINT = "❌ BOT_TOKEN не задан — выполните: just set-token"

try:
    from app.config import settings  # noqa: E402
except Exception:
    # Текст исключения не печатаем: в нём могут оказаться значения из настроек.
    print(NO_TOKEN_HINT, file=sys.stderr)
    sys.exit(1)


async def dump(pack_name: str) -> int:
    try:
        async with Bot(token=settings.bot_token) as bot:
            sticker_set = await bot.get_sticker_set(name=pack_name)
    except TokenValidationError:
        print(NO_TOKEN_HINT, file=sys.stderr)
        return 1
    except Exception as e:
        # Страховка от утечки токена в тексте исключения (например, в URL запроса)
        print(f"❌ Не удалось получить пак {pack_name}: {str(e).replace(settings.bot_token, '•••')}", file=sys.stderr)
        return 1
    if sticker_set.sticker_type != "custom_emoji":
        print(f"❌ {pack_name} — это не эмодзи-пак (тип: {sticker_set.sticker_type})", file=sys.stderr)
        return 1
    print(f"# {sticker_set.title} ({pack_name}): {len(sticker_set.stickers)} стикеров")
    for sticker in sticker_set.stickers:
        print(f"{sticker.emoji or '?'}\t{sticker.custom_emoji_id}")
    return 0


if __name__ == "__main__":
    pack = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PACK
    sys.exit(asyncio.run(dump(pack)))
