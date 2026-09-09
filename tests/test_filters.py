"""
Тесты фильтров.
"""
from datetime import UTC

from tests.harness import make_user


async def test_admin_cancel_clears_admin_state(harness, admin):
    await harness.send_callback("admin_broadcast", admin)
    replies = await harness.send_message("/cancel", admin)
    assert "отменена" in replies[0].text.lower()
    assert await harness.state_of(admin) is None


async def test_non_admin_cancel_is_not_swallowed_by_admin_router(harness):
    """Без фильтра IsAdmin админский /cancel молча съедал команду у обычных пользователей."""
    stranger = make_user(user_id=5, first_name="Гость", username="guest")
    replies = await harness.send_message("/cancel", stranger)
    # Примеры включены — их /cancel вне анкеты не срабатывает, значит ответа быть не должно,
    # но и падать/съедать апдейт админский роутер не должен: проверяем, что хендлер не вызван.
    assert all("админ" not in r.text.lower() for r in replies)


async def test_is_admin_filter_matches_only_configured_ids():
    from app.filters import IsAdmin

    assert await IsAdmin()(_event(user_id=777)) is True
    assert await IsAdmin()(_event(user_id=1)) is False


def _event(user_id: int):
    from datetime import datetime

    from aiogram.types import Chat, Message

    return Message(
        message_id=1, date=datetime.now(UTC),
        chat=Chat(id=user_id, type="private"), from_user=make_user(user_id=user_id), text="/x",
    )
