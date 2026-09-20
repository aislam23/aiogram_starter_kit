# Кастомные эмодзи с автоматическим fallback — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Бот на шаблоне показывает иконки из пака custom emoji `tgiosicons` в текстах и inline-кнопках, а код хендлеров по-прежнему пишется обычными юникод-эмодзи; при отсутствии Telegram Premium у владельца бот сам переходит на обычные эмодзи и сам возвращается к иконкам.

**Architecture:** Чистый каталог `app/ui/icons.py` (ID иконок, маппинг юникод → ID, функции `emojify` / `iconify_markup`) + session-middleware `app/middlewares/custom_emoji.py`, который на выходе конвертирует `text`/`caption`/`reply_markup` всех исходящих методов и по ответу Telegram (`Message.entities`) или по `TelegramBadRequest` определяет, есть ли право на custom emoji. Состояние — singleton `custom_emoji_status` в процессе (как `liveness`), с повторной попыткой раз в 24 ч. Спека: `docs/superpowers/specs/2026-09-19-custom-emoji-design.md` — читать перед началом.

**Tech Stack:** Python 3.11, aiogram 3.31 (Bot API 9.4: `icon_custom_emoji_id`), pydantic 2, pytest + харнес `tests/harness.py`. Проверка — `just check` (ruff + pytest + secrets scan).

**Правила репозитория (обязательно):** комментарии, докстринги и тексты для пользователя — по-русски, идентификаторы — по-английски. `just check` после каждой задачи, красный — не коммитить. Не читать `.env*` (в `.claude/settings.json` запрет; `.env.example` тоже под него попадает — в задаче 9 он дописывается `printf >>`, без чтения). Коммиты — с атрибуцией из system-reminder текущей сессии.

---

## Структура файлов

| Файл | Действие | Ответственность |
|---|---|---|
| `requirements.txt`, `AGENTS.md:40` | изменить | aiogram 3.20 → 3.31 |
| `scripts/dump_emoji_pack.py` | создать | Выгрузка `эмодзи → custom_emoji_id` любого пака через `settings.bot_token` |
| `justfile`, `Makefile` | изменить | Рецепт `emoji-dump [pack]` |
| `app/ui/__init__.py`, `app/ui/icons.py` | создать | Каталог `Icons`, `EMOJI_TO_ICON`, `SUPPORTED_EMOJI`, `emoji()`, `emojify()`, `strip_leading_emoji()`, `iconify_markup()` — без состояния |
| `app/config.py` | изменить | `CUSTOM_EMOJI=auto\|off` |
| `app/middlewares/custom_emoji.py` | создать | `CustomEmojiStatus` + `custom_emoji_status` (singleton), `CustomEmojiMiddleware`, уведомление админов |
| `app/main.py` | изменить | Регистрация middleware на `bot.session` |
| `app/handlers/admin/admin.py` | изменить | Строка «Иконки: …» в `/admin` |
| `tests/harness.py`, `tests/conftest.py` | изменить | `DefaultBotProperties(parse_mode=HTML)`, middleware на боте харнеса, `FakeSession.premium_entities` / `reject`, `harness.premium(mode)`, teardown |
| `tests/test_icons.py` | создать | Чистые функции каталога + инвентарь эмодзи |
| `tests/test_custom_emoji.py` | создать | Middleware через харнес |
| `tests/test_handlers.py` | изменить | Проверка строки «Иконки» в `/admin` |
| `AGENTS.md`, `CLAUDE.md`, `README.md`, `.env.example` | изменить | Раздел «Эмодзи и иконки», правило для агента |

---

### Task 1: Апгрейд aiogram до 3.31.0

**Files:**
- Modify: `requirements.txt:1`
- Modify: `AGENTS.md:40`

- [ ] **Step 1: Поднять версию**

В `requirements.txt` заменить строку `aiogram==3.20.0.post0` на `aiogram==3.31.0`.
В `AGENTS.md` строку 40 `Стек: Python 3.11, aiogram 3.20, ...` → `Стек: Python 3.11, aiogram 3.31, ...`.

- [ ] **Step 2: Переустановить зависимости в venv**

Run: `.venv/bin/pip install -q -r requirements-dev.txt && .venv/bin/pip show aiogram | head -2`
Expected: `Version: 3.31.0`

- [ ] **Step 3: Убедиться, что поле кнопки есть**

Run: `.venv/bin/python -c "from aiogram.types import InlineKeyboardButton as B; print('icon_custom_emoji_id' in B.model_fields)"`
Expected: `True`

- [ ] **Step 4: Полная проверка**

Run: `just check`
Expected: ruff без ошибок, все тесты PASS, секретов не найдено. Если что-то упало из-за апгрейда — починить в рамках этой задачи (в 3.x между 3.20 и 3.31 используемые API — Router, FSM, RedisStorage, session middleware — совместимы).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt AGENTS.md
git commit -m "chore: aiogram 3.31 — нужен icon_custom_emoji_id для кнопок (Bot API 9.4)"
```

---

### Task 2: Скрипт выгрузки пака и рецепт `just emoji-dump`

**Files:**
- Create: `scripts/dump_emoji_pack.py`
- Modify: `justfile` (рядом с `logs-json`, ~строка 450)
- Modify: `Makefile` (рядом с `check`, ~строка 312)

- [ ] **Step 1: Написать скрипт**

```python
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
```

- [ ] **Step 2: Рецепты**

В `justfile` после рецепта `logs-json`:

```make
# Print «emoji → custom_emoji_id» of a Telegram emoji pack (usage: just emoji-dump tgiosicons)
emoji-dump pack="tgiosicons":
    {{venv_python}} scripts/dump_emoji_pack.py {{pack}}
```

В `Makefile` после `check:`:

```make
emoji-dump: _check-python ## 🎨 Print «emoji → custom_emoji_id» of a pack (PACK=tgiosicons)
	@$(VENV_PYTHON) scripts/dump_emoji_pack.py $(or $(PACK),tgiosicons)
```

- [ ] **Step 3: Проверить вручную**

Run: `just emoji-dump tgiosicons | head -3`
Expected: первая строка `# Telegram iOS Icons (tgiosicons): 399 стикеров`, дальше строки вида `💬	6030784887093464891`. Токен в выводе отсутствует.

- [ ] **Step 4: `just check` и commit**

Run: `just check` → зелёный.

```bash
git add scripts/dump_emoji_pack.py justfile Makefile
git commit -m "feat: just emoji-dump — выгрузка ID custom emoji из пака"
```

---

### Task 3: Каталог иконок и `emojify`

**Files:**
- Create: `app/ui/__init__.py`
- Create: `app/ui/icons.py`
- Test: `tests/test_icons.py`

- [ ] **Step 1: Написать падающие тесты**

`tests/test_icons.py`:

```python
"""
Тесты каталога custom emoji: чистые функции без Telegram и харнеса.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.ui.icons import (
    EMOJI_TO_ICON,
    SUPPORTED_EMOJI,
    Icons,
    emojify,
    iconify_markup,
    strip_leading_emoji,
)

TG = '<tg-emoji emoji-id="{id}">{fallback}</tg-emoji>'


# ── emojify ─────────────────────────────────────────────────────


def test_emojify_replaces_known_emoji_with_fallback_inside_tag():
    assert emojify("✅ Готово") == TG.format(id=Icons.CHECK, fallback="✅") + " Готово"


def test_emojify_handles_variation_selector_both_ways():
    with_vs16 = emojify("⚠️ Внимание")
    without_vs16 = emojify("⚠ Внимание")
    assert with_vs16 == TG.format(id=Icons.WARNING, fallback="⚠️") + " Внимание"
    assert without_vs16 == TG.format(id=Icons.WARNING, fallback="⚠") + " Внимание"


def test_emojify_is_idempotent():
    once = emojify("📊 Статистика ✅")
    assert emojify(once) == once


def test_emojify_leaves_unknown_emoji_alone():
    assert emojify("🍳 Завтрак") == "🍳 Завтрак"


def test_emojify_skips_code_and_pre_blocks():
    text = "✅ ok <code>✅ raw</code> и <pre>📊\nблок</pre> 📊"
    result = emojify(text)
    assert "<code>✅ raw</code>" in result
    assert "<pre>📊\nблок</pre>" in result
    assert result.startswith(TG.format(id=Icons.CHECK, fallback="✅"))
    assert result.endswith(TG.format(id=Icons.STATS, fallback="📊"))


def test_emojify_replaces_substitute_icons_but_keeps_original_fallback():
    # 🩺 в паке нет — ставится иконка-заменитель, а fallback остаётся исходным эмодзи
    assert emojify("🩺 Проверка") == TG.format(id=Icons.HEALTH, fallback="🩺") + " Проверка"


# ── strip_leading_emoji / iconify_markup ─────────────────────────


def test_strip_leading_emoji_returns_rest_and_emoji():
    assert strip_leading_emoji("📊 Рассылка") == ("Рассылка", "📊")
    assert strip_leading_emoji("⬅️Назад") == ("Назад", "⬅️")


def test_strip_leading_emoji_ignores_unknown_or_non_leading():
    assert strip_leading_emoji("Рассылка 📊") == ("Рассылка 📊", None)
    assert strip_leading_emoji("🍳 Завтрак") == ("🍳 Завтрак", None)


def test_strip_leading_emoji_keeps_emoji_only_text():
    # Кнопка «◀️» пагинации: без текста Telegram кнопку отвергнет — не трогаем
    assert strip_leading_emoji("◀️") == ("◀️", None)


def test_iconify_markup_moves_emoji_to_icon_field():
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Рассылка", callback_data="a")],
        [InlineKeyboardButton(text="Без эмодзи", callback_data="b"),
         InlineKeyboardButton(text="◀️", callback_data="c")],
    ])
    result, changed = iconify_markup(markup)
    assert changed == 1
    first = result.inline_keyboard[0][0]
    assert (first.text, first.icon_custom_emoji_id, first.callback_data) == ("Рассылка", Icons.STATS, "a")
    assert result.inline_keyboard[1][0].text == "Без эмодзи"
    assert result.inline_keyboard[1][0].icon_custom_emoji_id is None
    assert result.inline_keyboard[1][1].text == "◀️"
    # Исходная клавиатура не изменена
    assert markup.inline_keyboard[0][0].text == "📊 Рассылка"


def test_iconify_markup_skips_buttons_with_icon_already_set():
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Рассылка", callback_data="a", icon_custom_emoji_id="1")],
    ])
    result, changed = iconify_markup(markup)
    assert changed == 0
    assert result is markup


def test_iconify_markup_leaves_reply_keyboard_untouched():
    markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]])
    result, changed = iconify_markup(markup)
    assert (result, changed) == (markup, 0)


# ── согласованность каталога ─────────────────────────────────────


def test_catalog_ids_are_digit_strings_and_map_keys_reference_icons():
    icon_ids = {v for k, v in vars(Icons).items() if k.isupper()}
    assert icon_ids, "каталог пуст"
    for icon_id in icon_ids:
        assert isinstance(icon_id, str) and icon_id.isdigit(), icon_id
    for emoji_char, icon_id in EMOJI_TO_ICON.items():
        assert icon_id in icon_ids, f"{emoji_char!r} ссылается на неизвестный ID {icon_id}"


def test_supported_emoji_are_all_mapped_and_unique():
    assert len(SUPPORTED_EMOJI) == len(set(SUPPORTED_EMOJI))
    for emoji_char in SUPPORTED_EMOJI:
        assert emoji_char in EMOJI_TO_ICON
        assert emoji_char.replace("\ufe0f", "") in EMOJI_TO_ICON
        assert emoji_char.replace("\ufe0f", "") + "\ufe0f" in EMOJI_TO_ICON
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv/bin/python -m pytest tests/test_icons.py -q`
Expected: ошибка импорта `ModuleNotFoundError: No module named 'app.ui'`.

- [ ] **Step 3: Создать каталог**

`app/ui/__init__.py`:

```python
"""
UI-слой без состояния: каталог custom emoji (icons.py).
"""
```

`app/ui/icons.py`:

```python
"""
Кастомные (premium) эмодзи из пака tgiosicons (https://t.me/addemoji/tgiosicons).

В коде бота пишутся обычные юникод-эмодзи из SUPPORTED_EMOJI. На выходе CustomEmojiMiddleware
(app/middlewares/custom_emoji.py) превращает их в custom emoji:
- тексты и подписи — HTML-тег <tg-emoji emoji-id="…">✅</tg-emoji> (Bot API 6.2). Обычный эмодзи
  внутри тега обязателен: его показывают клиенты там, где custom emoji недоступен;
- inline-кнопки — поле icon_custom_emoji_id (Bot API 9.4), эмодзи из текста кнопки вырезается.

Иконки видны, если у владельца бота активен Telegram Premium; без него Telegram убирает entity,
а middleware переключается на обычные эмодзи. Этот модуль — чистый каталог без состояния.
ID выгружаются командой `just emoji-dump tgiosicons`.
"""
import re
from typing import Optional

from aiogram.types import InlineKeyboardMarkup


class Icons:
    """ID custom emoji из пака tgiosicons. В комментарии — какой эмодзи заменяет и где используется.

    Если у эмодзи нет аналога в паке, взята ближайшая по смыслу иконка (помечено «для …»).
    """

    CHECK = "5774022692642492953"     # ✅ подтверждение, «живых», «готово»
    ONLINE = "6041919344995209164"    # ✅ (для 🟢 статус «работает», Local API)
    CROSS = "5774077015388852135"     # ❌ отмена, ошибка, «нет прав»
    BLOCK = "5938215362473496448"     # 🚫 заблокировали бота, запрет
    MINUS = "5938071395169734715"     # 🚫 (для ➖ снять права/удалить — минуса в паке нет)
    STATS = "5936143551854285132"     # 📊 статистика, рассылка
    CHART = "5938539885907415367"     # 📈 успешность, график
    USERS = "6032609071373226027"     # 👥 пользователи, администраторы
    USER = "6032994772321309200"      # 👤 пользователь, профиль
    CROWN = "5805553606635559688"     # 👑 суперадмин / админ из .env
    WAVE = "6041921818896372382"      # 👋 приветствие
    GHOST = "5812150667812280629"     # 🫥 (для 👻 удалённый аккаунт)
    HEALTH = "6050677620830376838"    # 💊 (для 🩺 проверка живых)
    UPLOAD = "6039573425268201570"    # 📤 рассылка, отправить
    INBOX = "6041730074376410123"     # 📥 входящее
    NOTE = "5920046907782074235"      # 📝 текст, заметка
    LIST = "5766994197705921104"      # 🗂 (для 📋 список, команды)
    LINK = "6028171274939797252"      # 🔗 ссылка
    WRENCH = "5962952497197748583"    # 🔧 админка, настройка
    GEAR = "5850224242926295392"      # ⚙️ настройки API
    REFRESH = "5769248574499983619"   # 🔄 обновить
    BACK = "5960671702059848143"      # ⬅️ назад (и для ◀️)
    PLAY = "5773626993010546707"      # ▶️ вперёд, запустить
    PLUS = "6032924188828767321"      # ➕ добавить
    WARNING = "6030563507299160824"   # ❗️ (для ⚠️ предупреждение, ошибки)
    HELP = "6030848053177486888"      # ❓ (для 🆘 помощь)
    INFO = "6028435952299413210"      # ℹ️ информация
    ZAP = "5920515922505765329"       # ⚡️ (для 🚀 Redis / запуск)
    SIGNAL = "6048723247501938454"    # 🛜 (для 📡 API Telegram)
    GLOBE = "5776233299424843260"     # 🌐 (для 🌍 Public API)
    HOME = "6042137469204303531"      # 🏠 среда, дом
    DATABASE = "5778672437122045013"  # 📦 (для 🗄️ база данных)
    CLOCK = "5775896410780079073"     # 🕓 (для 🕐 время запуска)
    ALARM = "5850317551090800862"     # ⏰ время проверки
    TIMER = "6037268453759389862"     # ⏲️ (для ⏱ длительность)
    STOP = "5771652845652677093"      # 🔳 (для ⏹ остановить)
    CHAT = "6030784887093464891"      # 💬 сообщение, вопросы
    CAKE = "5922305158636639117"      # 🎂 возраст (пример анкеты)


# Канонический вид эмодзи (как принято писать в коде) → ID иконки.
# Порядок — порядок в документации (SUPPORTED_EMOJI).
_CANONICAL: dict[str, str] = {
    "✅": Icons.CHECK,
    "❌": Icons.CROSS,
    "⚠️": Icons.WARNING,
    "ℹ️": Icons.INFO,
    "🆘": Icons.HELP,
    "📊": Icons.STATS,
    "📈": Icons.CHART,
    "👥": Icons.USERS,
    "👤": Icons.USER,
    "👑": Icons.CROWN,
    "👋": Icons.WAVE,
    "👻": Icons.GHOST,
    "🩺": Icons.HEALTH,
    "🚫": Icons.BLOCK,
    "➖": Icons.MINUS,
    "➕": Icons.PLUS,
    "📤": Icons.UPLOAD,
    "📥": Icons.INBOX,
    "📝": Icons.NOTE,
    "📋": Icons.LIST,
    "🔗": Icons.LINK,
    "🔧": Icons.WRENCH,
    "⚙️": Icons.GEAR,
    "🔄": Icons.REFRESH,
    "⬅️": Icons.BACK,
    "◀️": Icons.BACK,
    "▶️": Icons.PLAY,
    "⏹": Icons.STOP,
    "⏰": Icons.ALARM,
    "⏱": Icons.TIMER,
    "🕐": Icons.CLOCK,
    "🟢": Icons.ONLINE,
    "🚀": Icons.ZAP,
    "📡": Icons.SIGNAL,
    "🌍": Icons.GLOBE,
    "🏠": Icons.HOME,
    "🗄️": Icons.DATABASE,
    "💬": Icons.CHAT,
    "🎂": Icons.CAKE,
}

_VS16 = "\ufe0f"

# Эмодзи, которые можно использовать в UI (канонический вид) — для документации и подсказок агенту
SUPPORTED_EMOJI: tuple[str, ...] = tuple(_CANONICAL)


def _with_variants(canonical: dict[str, str]) -> dict[str, str]:
    """Добавляет к каждому эмодзи варианты с VS16 и без него: в коде встречаются оба"""
    result: dict[str, str] = {}
    for emoji_char, icon_id in canonical.items():
        bare = emoji_char.replace(_VS16, "")
        result[emoji_char] = icon_id
        result[bare] = icon_id
        result[bare + _VS16] = icon_id
    return result


# Любой вид эмодзи из текста бота → ID иконки
EMOJI_TO_ICON: dict[str, str] = _with_variants(_CANONICAL)

# Длинные варианты (с VS16) должны матчиться раньше коротких
_EMOJI_RE = re.compile("|".join(sorted(map(re.escape, EMOJI_TO_ICON), key=len, reverse=True)))

# Фрагменты, внутри которых эмодзи не трогаем: уже сконвертированные теги и моноширинные блоки
_PROTECTED_RE = re.compile(
    r"<tg-emoji\s[^>]*>.*?</tg-emoji>|<(pre|code)(?:\s[^>]*)?>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

# Эмодзи в начале текста кнопки (+ пробелы после него)
_LEADING_EMOJI_RE = re.compile(rf"^({_EMOJI_RE.pattern})\s*")


def emoji(icon_id: str, fallback: str) -> str:
    """HTML custom emoji с fallback-эмодзи для клиентов, где иконка недоступна"""
    return f'<tg-emoji emoji-id="{icon_id}">{fallback}</tg-emoji>'


def _substitute(text: str) -> str:
    return _EMOJI_RE.sub(lambda m: emoji(EMOJI_TO_ICON[m.group(0)], m.group(0)), text)


def emojify(text: str) -> str:
    """Заменяет известные юникод-эмодзи в HTML-тексте на custom emoji, исходный эмодзи — fallback.

    Идемпотентна: содержимое уже существующих <tg-emoji>, а также <code> и <pre> не трогается.
    Применять только к тексту с parse_mode=HTML.
    """
    parts = []
    last = 0
    for m in _PROTECTED_RE.finditer(text):
        parts.append(_substitute(text[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(_substitute(text[last:]))
    return "".join(parts)


def strip_leading_emoji(text: str) -> tuple[str, Optional[str]]:
    """(текст без ведущего эмодзи, сам эмодзи) или (текст, None), если эмодзи нет или текст без него пуст"""
    m = _LEADING_EMOJI_RE.match(text)
    if not m:
        return text, None
    rest = text[m.end():]
    if not rest:
        return text, None
    return rest, m.group(1)


def iconify_markup(markup: object) -> tuple[object, int]:
    """Переносит ведущий эмодзи inline-кнопок в icon_custom_emoji_id.

    Возвращает (новая клавиатура, сколько кнопок изменено). Reply-клавиатуры и кнопки с уже
    заданной иконкой не трогаются; если ничего не изменилось — возвращается исходный объект.
    """
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup, 0
    changed = 0
    rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for button in row:
            rest, emoji_char = strip_leading_emoji(button.text)
            if emoji_char is None or button.icon_custom_emoji_id is not None:
                new_row.append(button)
                continue
            new_row.append(button.model_copy(update={"text": rest, "icon_custom_emoji_id": EMOJI_TO_ICON[emoji_char]}))
            changed += 1
        rows.append(new_row)
    if not changed:
        return markup, 0
    return InlineKeyboardMarkup(inline_keyboard=rows), changed
```

- [ ] **Step 4: Прогнать тесты**

Run: `.venv/bin/python -m pytest tests/test_icons.py -q`
Expected: все PASS. Если `test_emojify_handles_variation_selector_both_ways` падает на `⚠` без VS16 — проверить, что `_with_variants` добавил bare-вариант (ключ `"⚠"`).

- [ ] **Step 5: `just check` и commit**

```bash
git add app/ui tests/test_icons.py
git commit -m "feat(ui): каталог custom emoji tgiosicons, emojify и iconify_markup"
```

---

### Task 4: Инвентарный тест — все эмодзи UI есть в каталоге

**Files:**
- Modify: `tests/test_icons.py` (добавить в конец)

- [ ] **Step 1: Добавить тест**

В начало файла (к остальным импортам, по порядку isort — stdlib выше aiogram):

```python
import ast
import re
from pathlib import Path
```

В конец файла:

```python
# ── инвентарь: эмодзи в UI-строках должны быть в каталоге ────────

APP = Path(__file__).resolve().parent.parent / "app"
SCAN_DIRS = ("keyboards", "handlers", "services")
# Общий регекс по диапазонам Emoji (включая Geometric Shapes ◀️▶️) — чтобы ловить и те, которых каталог не знает
ANY_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2100-\u214F\u2300-\u25FF]\ufe0f?")
# Символы из этих диапазонов, которые эмодзи не являются или намеренно остаются обычными
INVENTORY_EXCEPTIONS = {"№", "≈", "→"}


def _ui_strings(path: Path):
    """Строковые литералы файла, кроме тех, что внутри вызовов logger.* (логи — не UI)"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    logged: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "logger":
                logged.update(id(n) for n in ast.walk(node))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in logged:
            yield node.value


def test_all_ui_emoji_are_in_catalog():
    unknown: dict[str, set[str]] = {}
    for sub in SCAN_DIRS:
        for path in (APP / sub).rglob("*.py"):
            for text in _ui_strings(path):
                for found in ANY_EMOJI_RE.findall(text):
                    if found in EMOJI_TO_ICON or found in INVENTORY_EXCEPTIONS:
                        continue
                    unknown.setdefault(found, set()).add(str(path.relative_to(APP)))
    assert not unknown, f"эмодзи вне каталога app/ui/icons.py: {unknown}"
```

- [ ] **Step 2: Прогнать**

Run: `.venv/bin/python -m pytest tests/test_icons.py::test_all_ui_emoji_are_in_catalog -q`
Expected: PASS. Если FAIL — в сообщении список эмодзи и файлов: либо добавить в `_CANONICAL` (взять ID из `just emoji-dump tgiosicons`, ближайший по смыслу), либо, если это не эмодзи (`№`, стрелка `→`), — в `INVENTORY_EXCEPTIONS`. **Не** менять тексты хендлеров ради теста.

- [ ] **Step 3: `just check` и commit**

```bash
git add tests/test_icons.py app/ui/icons.py
git commit -m "test(ui): инвентарь эмодзи UI сверяется с каталогом иконок"
```

---

### Task 5: Настройка `CUSTOM_EMOJI` и состояние `CustomEmojiStatus`

**Files:**
- Modify: `app/config.py` (после `timezone`, ~строка 53)
- Create: `app/middlewares/custom_emoji.py` (пока только состояние)
- Test: `tests/test_custom_emoji.py`

- [ ] **Step 1: Падающие тесты состояния**

`tests/test_custom_emoji.py`:

```python
"""
Тесты custom emoji: состояние (без Telegram) и middleware (через харнес).
"""
from datetime import UTC, datetime, timedelta

from app.middlewares.custom_emoji import RETRY_AFTER, CustomEmojiStatus


def test_status_enabled_by_default():
    status = CustomEmojiStatus()
    assert status.enabled is True
    assert status.retry_in is None


def test_disable_turns_off_and_records_reason():
    status = CustomEmojiStatus()
    assert status.disable("причина", bot=None) is True
    assert status.enabled is False
    assert status.reason == "причина"
    assert status.retry_in is not None and status.retry_in <= RETRY_AFTER


def test_disable_is_noop_while_already_disabled():
    status = CustomEmojiStatus()
    status.disable("первая", bot=None)
    assert status.disable("вторая", bot=None) is False
    assert status.reason == "первая"


def test_status_reenables_after_retry_period():
    status = CustomEmojiStatus()
    status.disable("причина", bot=None)
    status.disabled_at = datetime.now(UTC) - RETRY_AFTER - timedelta(seconds=1)
    assert status.enabled is True
    # …и disable снова срабатывает
    assert status.disable("снова", bot=None) is True


def test_reset_clears_everything():
    status = CustomEmojiStatus()
    status.disable("причина", bot=None)
    status.reset()
    assert status.enabled is True and status.reason is None and status.notify_task is None
```

- [ ] **Step 2: Убедиться, что падают**

Run: `.venv/bin/python -m pytest tests/test_custom_emoji.py -q`
Expected: `ModuleNotFoundError: No module named 'app.middlewares.custom_emoji'`.

- [ ] **Step 3: Настройка в `app/config.py`**

После поля `timezone` добавить:

```python
    # Custom emoji (app/ui/icons.py, app/middlewares/custom_emoji.py): auto — иконки из пака, если
    # у владельца бота есть Telegram Premium, иначе обычные эмодзи; off — всегда обычные эмодзи
    custom_emoji: str = Field("auto", alias="CUSTOM_EMOJI")
```

и валидатор рядом с существующими (стиль файла — `@validator`):

```python
    @validator('custom_emoji')
    def normalize_custom_emoji(cls, v):
        """auto | off, без учёта регистра; всё остальное считаем auto"""
        return "off" if str(v).strip().lower() == "off" else "auto"
```

- [ ] **Step 4: Состояние в `app/middlewares/custom_emoji.py`**

```python
"""
Session-middleware custom emoji: иконки из пака tgiosicons во всех исходящих сообщениях.

Хендлеры пишут обычные эмодзи (см. app/ui/icons.py). Здесь на выходе:
- text/caption → emojify() (только при parse_mode=HTML и без явных entities);
- inline reply_markup → iconify_markup() — у любого метода, где поле есть.

Право на custom emoji (Telegram Premium у владельца) определяется по живому трафику:
если Telegram вернул сообщение без custom_emoji entity или отверг метод с иконками —
статус выключается на RETRY_AFTER, бот шлёт обычные эмодзи, админам уходит уведомление.
По истечении RETRY_AFTER (или после рестарта) иконки пробуются снова — продление Premium
подхватывается без вмешательства.
"""
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Optional

from aiogram import Bot
from loguru import logger

from app.config import settings
from app.database import db

RETRY_AFTER = timedelta(hours=24)


class CustomEmojiStatus:
    """Есть ли сейчас право на custom emoji. Один на процесс (custom_emoji_status)"""

    def __init__(self) -> None:
        self.disabled_at: Optional[datetime] = None
        self.reason: Optional[str] = None
        self.notify_task: Optional[asyncio.Task] = None  # держим ссылку, иначе GC отменит задачу

    @property
    def enabled(self) -> bool:
        return self.disabled_at is None or datetime.now(UTC) - self.disabled_at >= RETRY_AFTER

    @property
    def retry_in(self) -> Optional[timedelta]:
        """Сколько осталось до следующей попытки включить иконки; None — иконки включены"""
        if self.enabled:
            return None
        return RETRY_AFTER - (datetime.now(UTC) - self.disabled_at)

    def disable(self, reason: str, bot: Optional[Bot]) -> bool:
        """Выключить иконки на RETRY_AFTER. No-op, если уже выключены. bot=None — без уведомления"""
        if not self.enabled:
            return False
        self.disabled_at = datetime.now(UTC)
        self.reason = reason
        logger.warning(f"Custom emoji выключены на {RETRY_AFTER}: {reason}")
        if bot is not None:
            self.notify_task = asyncio.create_task(notify_admins(bot, reason), name="custom-emoji-notify")
        return True

    def cancel_notify(self) -> None:
        if self.notify_task is not None and not self.notify_task.done():
            self.notify_task.cancel()
        self.notify_task = None

    def reset(self) -> None:
        self.cancel_notify()
        self.disabled_at = None
        self.reason = None

    def describe(self) -> tuple[str, str]:
        """(режим, пояснение) для /admin: («premium», «») / («обычные эмодзи», « (…)») / («выключены», « (…)»)"""
        if settings.custom_emoji == "off":
            return "выключены", " (CUSTOM_EMOJI=off)"
        if self.enabled:
            return "premium", ""
        hours = max(1, int(self.retry_in.total_seconds() // 3600))
        return "обычные эмодзи", f" (Premium не активен, проверим снова через {hours} ч)"


custom_emoji_status = CustomEmojiStatus()


async def notify_admins(bot: Bot, reason: str) -> None:
    """Сообщить админам (из настроек и назначенным через бота), что иконки выключены"""
    hours = int(RETRY_AFTER.total_seconds() // 3600)
    text = (
        "⚠️ <b>Иконки переключены на обычные эмодзи</b>\n\n"
        f"Telegram не принял custom emoji ({reason}). Обычно это значит, что у владельца бота "
        f"закончился Telegram Premium. Проверим снова через {hours} ч."
    )
    admin_ids = set(settings.admin_user_ids)
    try:
        admin_ids.update(admin.id for admin in await db.get_admins())
    except Exception as e:
        logger.warning(f"Не удалось получить список админов из базы: {e}")
    for admin_id in sorted(admin_ids):
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа {admin_id} о custom emoji: {e}")
```

- [ ] **Step 5: Прогнать тесты**

Run: `.venv/bin/python -m pytest tests/test_custom_emoji.py -q`
Expected: 5 PASS.

- [ ] **Step 6: `just check` и commit**

```bash
git add app/config.py app/middlewares/custom_emoji.py tests/test_custom_emoji.py
git commit -m "feat(custom-emoji): настройка CUSTOM_EMOJI и состояние с повторной попыткой раз в 24 ч"
```

---

### Task 6: Харнес — Premium-режимы, entities, отказы сессии

**Files:**
- Modify: `tests/harness.py`
- Modify: `tests/conftest.py:~215` (фикстура `harness`)

- [ ] **Step 1: Харнес**

В `tests/harness.py`:

1. Импорты — добавить:

```python
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MessageEntity
from app.middlewares.custom_emoji import CustomEmojiMiddleware, custom_emoji_status
```

(`Callable` — в `typing`-импорт; `import re` — к stdlib-импортам. Порядок импортов — по isort, иначе ruff I001.)

2. `FakeSession.__init__` — добавить поля:

```python
        # Режим custom emoji: отдавать ли custom_emoji entities за <tg-emoji> в тексте (Premium активен)
        self.premium_entities = False
        # Хук отказа: функция(method) -> исключение или None; None — запрос проходит
        self.reject: Optional[Callable[[TelegramMethod[Any]], Optional[Exception]]] = None
```

3. В `FakeSession.make_request` перед `self.calls.append(method)`:

```python
        if self.reject is not None:
            exc = self.reject(method)
            if exc is not None:
                raise exc
```

4. Хелпер уровня модуля (перед `FakeSession`):

```python
_TG_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="(\d+)">')


def custom_emoji_entities(text: Optional[str]) -> Optional[List[MessageEntity]]:
    """Как Telegram: по одной custom_emoji entity на каждый <tg-emoji> в тексте"""
    if not text:
        return None
    entities = [
        MessageEntity(type="custom_emoji", offset=i, length=2, custom_emoji_id=m.group(1))
        for i, m in enumerate(_TG_EMOJI_RE.finditer(text))
    ]
    return entities or None
```

(добавить `import re`).

5. В `_fake_response` для `SendMessage` и для `EditMessageText/EditMessageReplyMarkup` передать в `Message(...)`:

```python
                entities=custom_emoji_entities(method.text) if self.premium_entities else None,
```

(во второй ветке — `getattr(method, "text", None)`).

6. `BotHarness.__init__`: бот с дефолтным HTML и middleware, как в проде:

```python
        self.bot = Bot(
            token="42:TEST_TOKEN_FOR_TESTS_ONLY",
            session=self.session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.bot.session.middleware(CustomEmojiMiddleware())
```

7. Методы `BotHarness`:

```python
    def premium(self, mode: str) -> None:
        """Режим custom emoji.

        "off" — статус выключен заранее, конвертации нет (по умолчанию и после reset());
        "on"  — Premium активен: иконки конвертируются, сессия отдаёт custom_emoji entities;
        "lost" — статус включён, но entities не приходят (Premium закончился) — для теста детекции.
        """
        if mode not in ("off", "on", "lost"):
            raise ValueError(mode)
        custom_emoji_status.reset()
        self.session.premium_entities = mode == "on"
        if mode == "off":
            custom_emoji_status.disabled_at = datetime.now(UTC)

    @property
    def custom_emoji(self):
        """Состояние custom emoji (для проверок в тестах)"""
        return custom_emoji_status
```

и в `reset()` — добавить в конец `self.session.reject = None` и `self.premium("off")`.

- [ ] **Step 2: Teardown в conftest**

Фикстура `harness` становится yield-фикстурой:

```python
@pytest.fixture
def harness(fake_db, _harness_singleton) -> BotHarness:
    """Dispatcher + Bot с фейковой сессией. База уже подменена, состояние чистое."""
    _harness_singleton.reset()
    yield _harness_singleton
    # Фоновое уведомление админов о custom emoji не должно пережить откат fake_db
    _harness_singleton.custom_emoji.cancel_notify()
```

- [ ] **Step 3: Заглушка middleware, чтобы импорт работал**

Временно (до задачи 7) в `app/middlewares/custom_emoji.py` добавить минимальный класс — пропускающий всё:

```python
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response, TelegramType


class CustomEmojiMiddleware(BaseRequestMiddleware):
    """Подменяет юникод-эмодзи на custom emoji во всех исходящих сообщениях"""

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        return await make_request(bot, method)
```

- [ ] **Step 4: Все существующие тесты по-прежнему зелёные**

Run: `just check`
Expected: зелёный (режим `off` по умолчанию — поведение не изменилось).

- [ ] **Step 5: Commit**

```bash
git add tests/harness.py tests/conftest.py app/middlewares/custom_emoji.py
git commit -m "test(harness): режимы Premium для custom emoji, entities и отказы фейковой сессии"
```

---

### Task 7: `CustomEmojiMiddleware` — конвертация, детекция, повтор

**Files:**
- Modify: `app/middlewares/custom_emoji.py`
- Modify: `tests/test_custom_emoji.py` (добавить)

- [ ] **Step 1: Падающие тесты middleware**

Добавить в `tests/test_custom_emoji.py`. Импорты — **в начало файла**, к существующим (порядок isort: stdlib, третьи, `app`):

```python
import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import MessageEntity

from app.ui.icons import Icons
```

Тесты — в конец файла:

```python
TG = '<tg-emoji emoji-id="{id}">{fallback}</tg-emoji>'


def _icons_of(method):
    return [btn.icon_custom_emoji_id for row in method.reply_markup.inline_keyboard for btn in row]


async def test_premium_on_converts_text_and_buttons(harness, admin):
    harness.premium("on")
    replies = await harness.send_message("/admin", admin)
    msg = replies[0]
    assert TG.format(id=Icons.WRENCH, fallback="🔧") in msg.text
    assert "🔧 <b>" not in msg.text
    first = msg.reply_markup.inline_keyboard[0][0]
    assert (first.text, first.icon_custom_emoji_id) == ("Рассылка", Icons.STATS)
    assert harness.custom_emoji.enabled is True


async def test_premium_off_leaves_everything_plain(harness, admin):
    replies = await harness.send_message("/admin", admin)
    msg = replies[0]
    assert "<tg-emoji" not in msg.text
    assert msg.reply_markup.inline_keyboard[0][0].text == "📊 Рассылка"
    assert _icons_of(msg) == [None] * len(_icons_of(msg))


async def test_premium_lost_is_detected_and_admins_notified_once(harness, admin, fake_db):
    harness.premium("lost")
    await harness.send_message("/admin", admin)
    assert harness.custom_emoji.enabled is False
    assert "custom_emoji" in harness.custom_emoji.reason

    await harness.custom_emoji.notify_task
    notices = [c for c in harness.calls if isinstance(c, SendMessage) and "Иконки переключены" in (c.text or "")]
    assert len(notices) == 1 and notices[0].chat_id == admin.id
    assert "<tg-emoji" not in notices[0].text  # уведомление тоже обычными эмодзи

    # Следующие сообщения — уже обычными эмодзи, без повторного уведомления
    harness.clear()
    replies = await harness.send_message("/admin", admin)
    assert "<tg-emoji" not in replies[0].text
    assert replies[0].reply_markup.inline_keyboard[0][0].text == "📊 Рассылка"
    assert not any("Иконки переключены" in (c.text or "") for c in harness.calls if isinstance(c, SendMessage))


async def test_bad_request_on_icons_retries_plain_and_disables(harness, admin):
    harness.premium("on")

    def reject_icons(method):
        if "<tg-emoji" in (getattr(method, "text", None) or ""):
            return TelegramBadRequest(method=method, message="Bad Request: CUSTOM_EMOJI_INVALID")
        return None

    harness.session.reject = reject_icons
    replies = await harness.send_message("/admin", admin)
    assert len(replies) == 1 and "<tg-emoji" not in replies[0].text  # ушёл повтор без иконок
    assert harness.custom_emoji.enabled is False
    assert "CUSTOM_EMOJI_INVALID" in harness.custom_emoji.reason


async def test_bad_request_on_both_attempts_is_raised_and_keeps_status(harness, admin):
    harness.premium("on")
    harness.session.reject = lambda m: TelegramBadRequest(method=m, message="Bad Request: can't parse entities")
    # В проекте нет errors-хендлера: исключение хендлера вылетает из feed_update
    with pytest.raises(TelegramBadRequest):
        await harness.send_message("/admin", admin)
    assert harness.sent == []
    assert harness.custom_emoji.enabled is True


async def test_not_modified_is_not_retried(harness, admin):
    harness.premium("on")
    calls = []

    def reject_all(method):
        calls.append(method)
        return TelegramBadRequest(method=method, message="Bad Request: message is not modified")

    harness.session.reject = reject_all
    with pytest.raises(TelegramBadRequest):
        await harness.send_message("/admin", admin)
    assert len(calls) == 1  # без повтора
    assert harness.custom_emoji.enabled is True


async def test_markdown_or_explicit_entities_are_not_converted(harness):
    harness.premium("on")
    await harness.bot.send_message(1, "✅ md", parse_mode="Markdown")
    await harness.bot.send_message(1, "✅ ent", entities=[MessageEntity(type="bold", offset=0, length=1)])
    texts = [c.text for c in harness.calls if isinstance(c, SendMessage)]
    assert texts == ["✅ md", "✅ ent"]


async def test_retry_period_reenables_conversion(harness, admin):
    harness.premium("on")
    harness.custom_emoji.disable("тест", bot=None)
    harness.custom_emoji.disabled_at = datetime.now(UTC) - RETRY_AFTER - timedelta(seconds=1)
    replies = await harness.send_message("/admin", admin)
    assert "<tg-emoji" in replies[0].text
```

- [ ] **Step 2: Убедиться, что падают**

Run: `.venv/bin/python -m pytest tests/test_custom_emoji.py -q`
Expected: тесты `premium_on`, `premium_lost`, `bad_request_*`, `retry_period` — FAIL (заглушка ничего не конвертирует).

- [ ] **Step 3: Реализация middleware**

Заменить заглушку в `app/middlewares/custom_emoji.py` (импорты — дополнить):

```python
from aiogram.client.default import Default
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendInvoice
from aiogram.types import InlineKeyboardMarkup, Message

from app.ui.icons import emojify, iconify_markup


def _resolve_parse_mode(bot: Bot, method: TelegramMethod) -> Optional[str]:
    """parse_mode метода с учётом дефолта бота; None — у метода нет parse_mode"""
    value = getattr(method, "parse_mode", None)
    if isinstance(value, Default):
        value = bot.default.parse_mode
    # ParseMode — str-Enum: value.upper() даёт "HTML", а str(value) дал бы "ParseMode.HTML"
    return value.upper() if isinstance(value, str) else None


def _convert(bot: Bot, method: TelegramMethod) -> tuple[Optional[TelegramMethod], bool]:
    """(метод с иконками или None, если менять нечего; вставили ли <tg-emoji> в текст)"""
    update: dict = {}
    injected_text = False

    explicit_entities = getattr(method, "entities", None) or getattr(method, "caption_entities", None)
    if _resolve_parse_mode(bot, method) == "HTML" and not explicit_entities:
        for field in ("text", "caption"):
            value = getattr(method, field, None)
            if isinstance(value, str):
                converted = emojify(value)
                if converted != value:
                    update[field] = converted
                    injected_text = True

    markup = getattr(method, "reply_markup", None)
    if isinstance(markup, InlineKeyboardMarkup):
        new_markup, changed = iconify_markup(markup)
        if changed:
            update["reply_markup"] = new_markup

    if not update:
        return None, False
    return method.model_copy(update=update), injected_text


def _has_custom_emoji(message: Message) -> bool:
    entities = (message.entities or []) + (message.caption_entities or [])
    return any(entity.type == "custom_emoji" for entity in entities)


class CustomEmojiMiddleware(BaseRequestMiddleware):
    """Подменяет юникод-эмодзи на custom emoji во всех исходящих сообщениях"""

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        # Инвойс: первая кнопка — Pay, поведение иконок там неизвестно; entities не поддерживаются
        if isinstance(method, SendInvoice) or not custom_emoji_status.enabled:
            return await make_request(bot, method)

        converted, injected_text = _convert(bot, method)
        if converted is None:
            return await make_request(bot, method)

        try:
            result = await make_request(bot, converted)
        except TelegramBadRequest as e:
            if "message is not modified" in e.message:
                # Штатная ошибка (повторное нажатие, тот же прогресс): повтор стёр бы иконки с экрана
                raise
            # Повтор исходным методом: упадёт и он — ошибка не наша, пробрасываем первую
            try:
                result = await make_request(bot, method)
            except TelegramBadRequest:
                raise e from None
            custom_emoji_status.disable(f"Telegram отверг сообщение с иконками: {e.message}", bot)
            return result

        if injected_text and isinstance(result, Message) and not _has_custom_emoji(result):
            custom_emoji_status.disable("в ответе Telegram нет custom_emoji entity", bot)
        return result
```

- [ ] **Step 4: Прогнать тесты**

Run: `.venv/bin/python -m pytest tests/test_custom_emoji.py -q`
Expected: все PASS. Типичные причины падений:
- `premium_on`: `bot.default.parse_mode` — убедиться, что харнес создаёт бота с `DefaultBotProperties` (задача 6);
- `premium_lost`: `notify_task` — `None`: `disable()` вызван с `bot=None`? В middleware передаётся `bot`;
- ruff `B` про `except … raise` — использовать `raise` без аргумента, как в коде выше.

- [ ] **Step 5: `just check` и commit**

```bash
git add app/middlewares/custom_emoji.py tests/test_custom_emoji.py
git commit -m "feat(custom-emoji): middleware — иконки в текстах и кнопках, детекция Premium, fallback"
```

---

### Task 8: Подключение в `main.py` и строка в `/admin`

**Files:**
- Modify: `app/main.py:60-66` (после создания `bot`)
- Modify: `app/handlers/admin/admin.py:53-73` (`admin_panel_text`)
- Modify: `tests/test_handlers.py` (добавить тест)

- [ ] **Step 1: Падающий тест**

В `tests/test_handlers.py`:

```python
async def test_admin_panel_shows_custom_emoji_status(harness, admin, fake_db, monkeypatch):
    from app.config import settings

    replies = await harness.send_message("/admin", admin)
    assert "Иконки: <b>обычные эмодзи</b>" in replies[0].text

    harness.premium("on")
    replies = await harness.send_message("/admin", admin)
    assert "Иконки: <b>premium</b>" in replies[0].text

    monkeypatch.setattr(settings, "custom_emoji", "off")
    replies = await harness.send_message("/admin", admin)
    assert "Иконки: <b>выключены</b> (CUSTOM_EMOJI=off)" in replies[0].text
```

Run: `.venv/bin/python -m pytest tests/test_handlers.py::test_admin_panel_shows_custom_emoji_status -q` → FAIL (строки нет).

- [ ] **Step 2: Строка в `/admin`**

В `app/handlers/admin/admin.py` импорт `from app.middlewares.custom_emoji import custom_emoji_status`; в начале `admin_panel_text()` — `icons_label, icons_note = custom_emoji_status.describe()`, и в f-строке после `🕐 Последний запуск: …` добавить строку:

```
⚙️ Иконки: <b>{icons_label}</b>{icons_note}
```

- [ ] **Step 3: Регистрация в `main.py`**

После создания `bot` в `setup_bot()`:

```python
    # Иконки из пака custom emoji во всех исходящих сообщениях (app/middlewares/custom_emoji.py)
    if settings.custom_emoji != "off":
        bot.session.middleware(CustomEmojiMiddleware())
```

с импортом `from app.middlewares.custom_emoji import CustomEmojiMiddleware`.

- [ ] **Step 4: Тесты и `just check`**

Run: `just check` → зелёный.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/handlers/admin/admin.py app/middlewares/custom_emoji.py tests/test_handlers.py
git commit -m "feat(custom-emoji): подключение middleware и статус иконок в /admin"
```

---

### Task 9: Документация и `.env.example`

**Files:**
- Modify: `AGENTS.md` (таблица §1, новый рецепт §4.13, §5 «Чего не делать»)
- Modify: `CLAUDE.md` (короткое правило)
- Modify: `README.md` (раздел «Конфигурация», ~строка 315)
- Modify: `.env.example` (только append, без чтения)

- [ ] **Step 1: AGENTS.md**

В таблицу §1 после строки «Клавиатуры»:

```
| Иконки | `app/ui/icons.py`, `app/middlewares/custom_emoji.py` | Custom emoji из пака tgiosicons: в коде — обычные эмодзи из `SUPPORTED_EMOJI`, middleware конвертирует на выходе; без Premium у владельца — обычные эмодзи автоматически |
```

Новый рецепт после §4.12:

```markdown
### 4.13 Эмодзи и иконки

В кнопках и текстах пиши **обычные эмодзи из списка `SUPPORTED_EMOJI`** в `app/ui/icons.py`.
На выходе `CustomEmojiMiddleware` сам превратит их в иконки пака tgiosicons: в тексте — тег
`<tg-emoji>` (fallback — исходный эмодзи), в inline-кнопке — `icon_custom_emoji_id`
(эмодзи должен быть первым символом текста кнопки). Если у владельца нет Telegram Premium,
Telegram иконки не примет — middleware это заметит и переключится на обычные эмодзи,
админам придёт уведомление; через 24 ч попробует снова. Статус виден в `/admin`.

- Нужен эмодзи, которого нет в списке: сначала возьми ближайший из списка. Если не подходит —
  `just emoji-dump tgiosicons`, добавь ID в `Icons` и пару в `_CANONICAL` (`app/ui/icons.py`);
  тест `test_all_ui_emoji_are_in_catalog` подскажет, что осталось вне каталога.
- Не пиши `<tg-emoji>` и `icon_custom_emoji_id` руками.
- Reply-клавиатуры (`KeyboardButton`), `answer_callback_query`, инвойсы — обычные эмодзи,
  конвертации нет (текст reply-кнопки — это payload, который вернётся боту).
- Кнопка из одного эмодзи (`◀️`) остаётся как есть: без текста Telegram кнопку отвергнет.
- Выключить совсем: `CUSTOM_EMOJI=off` в `.env`.
```

В §5 «Чего не делать» добавить пункт:

```
- Не использовать в UI эмодзи вне `SUPPORTED_EMOJI` (`app/ui/icons.py`) и не писать `<tg-emoji>` / `icon_custom_emoji_id` руками — см. §4.13.
```

- [ ] **Step 2: CLAUDE.md**

В «Non-negotiable rules» после пункта про язык:

```
- Emoji in UI: only from `SUPPORTED_EMOJI` in `app/ui/icons.py`, written as plain unicode; the
  middleware turns them into custom emoji icons. Never hand-write `<tg-emoji>` or `icon_custom_emoji_id`
  (AGENTS.md §4.13).
```

- [ ] **Step 3: README.md**

В разделе «⚙️ Конфигурация» добавить строку про `CUSTOM_EMOJI` (в стиле соседних) и абзац:

```markdown
### 🎨 Иконки (custom emoji)

Бот использует иконки из пака [tgiosicons](https://t.me/addemoji/tgiosicons) вместо обычных
эмодзи — в текстах и кнопках. Для этого у владельца бота должен быть Telegram Premium. Если его
нет (или он закончился), бот сам переходит на обычные эмодзи и сообщает об этом админам; когда
Premium снова активен — иконки вернутся в течение суток. `CUSTOM_EMOJI=off` выключает иконки.
```

- [ ] **Step 4: `.env.example` — append без чтения**

Run:

```bash
printf '\n# Custom emoji: auto — иконки из пака, если у владельца бота есть Telegram Premium; off — обычные эмодзи\nCUSTOM_EMOJI=auto\n' >> .env.example
git diff --stat .env.example
```

Expected: `.env.example | 3 +++`. Содержимое файла не выводить.

- [ ] **Step 5: `just check` и commit**

```bash
git add AGENTS.md CLAUDE.md README.md .env.example
git commit -m "docs: эмодзи и иконки — правило для агента, CUSTOM_EMOJI, just emoji-dump"
```

---

### Task 10: Ручная проверка на живом боте и фиксация наблюдения

**Files:**
- Modify: `app/middlewares/custom_emoji.py` (комментарий по результату)

- [ ] **Step 1: Запустить бота и посмотреть `/admin`**

Run: `just dev-d && sleep 15 && just logs-json 30`
В Telegram у бота (`@aio_starter_kit_bot`) отправить `/admin`. Ожидание при активном Premium у владельца: кнопки с иконками, текст с иконками, строка «Иконки: premium». Без Premium: после первого сообщения в логах `Custom emoji выключены на 24:00:00: …`, админу пришло уведомление, следующий `/admin` — обычными эмодзи.

- [ ] **Step 2: Зафиксировать поведение сервера для кнопок**

Дописать в докстринг `CustomEmojiMiddleware` одно из: «Проверено <дата>: без Premium Telegram молча отбрасывает `icon_custom_emoji_id`, ошибки нет — детекция срабатывает по entities» или «…отвечает `Bad Request: <текст>` — срабатывает ветка повтора». Остановить бота: `just stop`.

- [ ] **Step 3: Финальный `just check` и commit**

```bash
git add app/middlewares/custom_emoji.py
git commit -m "docs(custom-emoji): наблюдение поведения Telegram для кнопок без Premium"
```
