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
