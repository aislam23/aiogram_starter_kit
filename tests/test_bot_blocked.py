"""
Флаг users.bot_blocked: кто заблокировал бота или удалил аккаунт.

«Живой» пользователь = is_active AND NOT bot_blocked — только таким шлём рассылки.
"""
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage

from app.services.broadcast import BroadcastService
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


class ForbiddenBot:
    async def send_message(self, chat_id: int, **kwargs):
        raise TelegramForbiddenError(method=SendMessage(chat_id=chat_id, text="x"), message="bot was blocked by the user")


class FakeTextMessage:
    text = "привет"
    html_text = "привет"
    photo = video = document = audio = voice = video_note = animation = sticker = None


async def test_broadcast_marks_user_blocked_on_forbidden(fake_db):
    await fake_db.add_user(5, username="five")
    service = BroadcastService(ForbiddenBot())  # type: ignore[arg-type]

    try:
        await service._send_single_message(user_id=5, message=FakeTextMessage())  # type: ignore[arg-type]
    except TelegramForbiddenError:
        pass  # сервис пробрасывает 403 наверх — там он считается как «заблокировал»

    assert fake_db.users[5].bot_blocked is True


async def test_broadcast_skips_users_who_blocked_bot(fake_db, monkeypatch):
    await fake_db.add_user(1)
    await fake_db.add_user(2)
    await fake_db.set_bot_blocked(2, True)
    sent: list[int] = []

    async def fake_send(self, user_id, message, custom_keyboard=None):
        sent.append(user_id)
        return True

    monkeypatch.setattr(BroadcastService, "_send_single_message", fake_send)
    stats = await BroadcastService(bot=None).send_broadcast(message=FakeTextMessage())  # type: ignore[arg-type]

    assert sent == [1]
    assert stats == {"total": 1, "sent": 1, "failed": 0, "blocked": 0}


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
