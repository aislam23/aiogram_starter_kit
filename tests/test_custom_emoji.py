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
