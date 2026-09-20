"""
Тесты каталога custom emoji: чистые функции без Telegram и харнеса.
"""
import ast
import re
from pathlib import Path

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


def test_emojify_empty_and_plain_text_unchanged():
    assert emojify("") == ""
    assert emojify("Просто текст без эмодзи") == "Просто текст без эмодзи"


def test_emojify_handles_trailing_and_adjacent_emoji():
    check = TG.format(id=Icons.CHECK, fallback="✅")
    assert emojify("Готово ✅") == "Готово " + check
    assert emojify("✅✅") == check + check


def test_emojify_converts_emoji_adjacent_to_tag_and_keeps_tag():
    assert emojify("✅<b>x</b>") == TG.format(id=Icons.CHECK, fallback="✅") + "<b>x</b>"


def test_emojify_does_not_touch_emoji_inside_tag_attributes():
    text = '<a href="https://x.com/📊">📊 link</a>'
    result = emojify(text)
    assert result.startswith('<a href="https://x.com/📊">')
    assert result == '<a href="https://x.com/📊">' + TG.format(id=Icons.STATS, fallback="📊") + " link</a>"


# ── strip_leading_emoji / iconify_markup ─────────────────────────


def test_strip_leading_emoji_returns_rest_and_emoji():
    assert strip_leading_emoji("📊 Рассылка") == ("Рассылка", "📊")
    assert strip_leading_emoji("⬅️Назад") == ("Назад", "⬅️")


def test_strip_leading_emoji_removes_only_first_emoji():
    assert strip_leading_emoji("✅✅ x") == ("✅ x", "✅")


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


# ── инвентарь: эмодзи в UI-строках должны быть в каталоге ────────

APP = Path(__file__).resolve().parent.parent / "app"
SCAN_DIRS = ("keyboards", "handlers", "services", "middlewares")
# Emoji-подмножества юникода (Misc Symbols, Dingbats, Arrows, Geometric Shapes ◀️▶️, ‼️⁉️, ©️®️ и т.д.) —
# чтобы ловить и те эмодзи, которых каталог не знает. Псевдографика (─ │ ● ■) намеренно не входит.
ANY_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2100-\u214F\u231A-\u231B\u23E9-\u23F3\u23F8-\u23FA\u25AA-\u25AB\u25B6\u25C0\u25FB-\u25FE\u203C\u2049\u2190-\u21FF\u2934-\u2935\u00A9\u00AE]\ufe0f?")
# Символы, которые регекс реально ловит, но эмодзи не являются или намеренно остаются обычными.
# Сюда попадают только те, что матчатся ANY_EMOJI_RE (см. test_inventory_exceptions_are_matched_by_regex).
INVENTORY_EXCEPTIONS = {"№", "→"}


def _root_name(node: ast.AST) -> str | None:
    """Имя в корне цепочки вызовов/атрибутов: logger.opt(...).error → "logger" """
    while isinstance(node, (ast.Attribute, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _ui_strings(path: Path):
    """Строковые литералы файла, кроме тех, что внутри вызовов logger.* (логи — не UI)"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    logged: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _root_name(node.func) == "logger":
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


def test_inventory_regex_matches_emoji_but_not_pseudographics():
    assert ANY_EMOJI_RE.findall("‼️ ⁉️ ↔️ ↩️ ⤴️ ©️ ®️ ◀️ ▶️ ⏹ ⏰") == [
        "‼️", "⁉️", "↔️", "↩️", "⤴️", "©️", "®️", "◀️", "▶️", "⏹", "⏰",
    ]
    assert ANY_EMOJI_RE.findall("─ │ ● ■ ◆ ▓ ① ⌘") == []


def test_inventory_exceptions_are_matched_by_regex():
    # мёртвые записи (которые регекс не ловит) бессмысленны — их не должно быть
    for symbol in INVENTORY_EXCEPTIONS:
        assert ANY_EMOJI_RE.fullmatch(symbol), symbol


def test_ui_strings_skip_logger_chains(tmp_path: Path):
    source = (
        "def f():\n"
        "    logger.info('🍳 лог')\n"
        "    logger.opt(exception=e).error('🍳 лог с opt')\n"
        "    return '🍳 ui'\n"
    )
    path = tmp_path / "m.py"
    path.write_text(source, encoding="utf-8")
    assert list(_ui_strings(path)) == ["🍳 ui"]

