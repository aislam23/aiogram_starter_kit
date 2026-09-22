"""
Флаг users.bot_blocked: кто заблокировал бота или удалил аккаунт.

«Живой» пользователь = is_active AND NOT bot_blocked — только таким шлём рассылки.
"""
from tests.harness import callbacks_of


async def test_blocking_bot_marks_user(harness, fake_db, user):
    await harness.send_message("/start", user)

    await harness.send_my_chat_member(user, blocked=True)

    assert fake_db.users[user.id].bot_blocked is True
    assert fake_db.users[user.id].bot_blocked_at is not None


async def test_unblocking_bot_clears_mark(harness, fake_db, user):
    await harness.send_message("/start", user)
    await harness.send_my_chat_member(user, blocked=True)

    await harness.send_my_chat_member(user, blocked=False)

    assert fake_db.users[user.id].bot_blocked is False
    assert fake_db.users[user.id].bot_blocked_at is None


async def test_writing_to_bot_clears_mark(harness, fake_db, user):
    """Пользователь снова пишет боту — значит, не блокирует его (даже если my_chat_member потерялся)."""
    await harness.send_message("/start", user)
    await fake_db.set_bot_blocked(user.id, True)

    await harness.send_message("привет", user)

    assert fake_db.users[user.id].bot_blocked is False


async def test_admin_panel_shows_alive_and_blocked_counts(harness, fake_db, admin, user):
    await harness.send_message("/start", admin)
    await harness.send_message("/start", user)
    await harness.send_my_chat_member(user, blocked=True)
    harness.clear()

    replies = await harness.send_message("/admin", admin)

    assert "Всего пользователей: <b>2</b>" in replies[0].text
    assert "Живых: <b>1</b>" in replies[0].text
    assert "Заблокировали бота: <b>1</b>" in replies[0].text
    assert "admin_liveness" in callbacks_of(replies[0])


async def test_broadcast_recipients_count_excludes_blocked(harness, fake_db, admin, user):
    await harness.send_message("/start", admin)
    await harness.send_message("/start", user)
    await harness.send_my_chat_member(user, blocked=True)
    await harness.send_callback("admin_broadcast", admin)
    harness.clear()

    replies = await harness.send_message("Текст рассылки", admin)

    assert "Количество получателей: <b>1</b>" in replies[0].text
