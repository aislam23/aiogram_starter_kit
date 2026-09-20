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
