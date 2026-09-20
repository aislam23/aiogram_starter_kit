"""
Тесты custom emoji: состояние (без Telegram) и middleware (через харнес).
"""
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import MessageEntity

from app.middlewares.custom_emoji import RETRY_AFTER, CustomEmojiStatus
from app.ui.icons import Icons


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
