"""
Выгрузка custom_emoji_id из эмодзи-пака Telegram.

    just emoji-dump [имя_пака]      # по умолчанию tgiosicons

Печатает по строке на стикер: «<эмодзи>\t<custom_emoji_id>». Токен берётся из настроек
(app/config.py) и не печатается. Результат используется для каталога app/ui/icons.py.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot  # noqa: E402

from app.config import settings  # noqa: E402

DEFAULT_PACK = "tgiosicons"


async def dump(pack_name: str) -> int:
    bot = Bot(token=settings.bot_token)
    try:
        sticker_set = await bot.get_sticker_set(name=pack_name)
    except Exception as e:
        print(f"❌ Не удалось получить пак {pack_name}: {e}", file=sys.stderr)
        return 1
    finally:
        await bot.session.close()
    print(f"# {sticker_set.title} ({pack_name}): {len(sticker_set.stickers)} стикеров")
    for sticker in sticker_set.stickers:
        print(f"{sticker.emoji}\t{sticker.custom_emoji_id}")
    return 0


if __name__ == "__main__":
    pack = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PACK
    sys.exit(asyncio.run(dump(pack)))
