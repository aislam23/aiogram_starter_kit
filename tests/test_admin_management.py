"""
Управление админами из бота: список, добавление через нативный выбор пользователя (request_users), снятие.
"""
from aiogram.methods import AnswerCallbackQuery
from aiogram.types import ReplyKeyboardRemove

from tests.harness import callbacks_of, make_user


async def _open_admins(harness, admin):
    await harness.send_message("/admin", admin)
    return await harness.send_callback("admin_manage", admin)


async def test_admin_menu_has_admins_button(harness, admin):
    replies = await harness.send_message("/admin", admin)
    assert "admin_manage" in callbacks_of(replies[0])


async def test_admins_screen_lists_env_admin_and_add_button(harness, admin):
    replies = await _open_admins(harness, admin)
    assert replies[0].__class__.__name__ == "EditMessageText"
    assert "Администраторы" in replies[0].text
    assert "777" in replies[0].text
    assert "из настроек" in replies[0].text
    assert "admins:add" in callbacks_of(replies[0])


async def test_non_admin_cannot_open_admins_screen(harness, user):
    replies = await harness.send_callback("admin_manage", user)
    assert replies == []


async def test_add_opens_native_user_picker(harness, admin):
    await _open_admins(harness, admin)
    replies = await harness.send_callback("admins:add", admin)

    assert await harness.state_of(admin) == "AdminStates:pick_admin"
    markup = replies[-1].reply_markup
    buttons = [b for row in markup.keyboard for b in row]
    picker = [b for b in buttons if b.request_users is not None]
    assert len(picker) == 1
    assert picker[0].request_users.user_is_bot is False
    assert picker[0].request_users.max_quantity == 1
    assert any("Отмена" in b.text for b in buttons)


async def test_shared_user_becomes_admin(harness, fake_db, admin):
    await _open_admins(harness, admin)
    await harness.send_callback("admins:add", admin)

    replies = await harness.send_users_shared(
        [{"user_id": 9009, "first_name": "Новый", "username": "newadmin"}], user=admin,
    )

    assert fake_db.users[9009].is_admin is True
    assert fake_db.users[9009].first_name == "Новый"
    assert await harness.state_of(admin) is None
    assert any(isinstance(r.reply_markup, ReplyKeyboardRemove) for r in replies)
    assert "9009" in replies[-1].text or "Новый" in replies[-1].text


async def test_new_admin_can_use_panel(harness, fake_db, admin):
    await _open_admins(harness, admin)
    await harness.send_callback("admins:add", admin)
    await harness.send_users_shared([{"user_id": 9009, "first_name": "Новый"}], user=admin)

    replies = await harness.send_message("/admin", make_user(user_id=9009, first_name="Новый", username=None))
    assert "Админская панель" in replies[0].text


async def test_cancel_button_closes_picker(harness, admin):
    await _open_admins(harness, admin)
    await harness.send_callback("admins:add", admin)

    replies = await harness.send_message("❌ Отмена", admin)

    assert await harness.state_of(admin) is None
    assert any(isinstance(r.reply_markup, ReplyKeyboardRemove) for r in replies)


async def test_users_shared_outside_picker_state_is_ignored(harness, fake_db, admin):
    replies = await harness.send_users_shared([{"user_id": 9010, "first_name": "X"}], user=admin)
    assert replies == []
    assert 9010 not in fake_db.users or not fake_db.users[9010].is_admin


async def test_remove_admin(harness, fake_db, admin):
    await fake_db.add_user(user_id=9009, username="newadmin", first_name="Новый")
    await fake_db.set_admin(9009)
    replies = await _open_admins(harness, admin)
    assert "admins:remove:9009" in callbacks_of(replies[0])

    replies = await harness.send_callback("admins:remove:9009", admin)

    assert fake_db.users[9009].is_admin is False
    assert "admins:remove:9009" not in callbacks_of(replies[0])


async def test_cannot_remove_yourself(harness, fake_db, admin):
    await fake_db.add_user(user_id=admin.id, username="admin", first_name="Админ")
    await fake_db.set_admin(admin.id)
    await _open_admins(harness, admin)

    await harness.send_callback(f"admins:remove:{admin.id}", admin)

    assert fake_db.users[admin.id].is_admin is True
    alerts = [c for c in harness.calls if isinstance(c, AnswerCallbackQuery) and c.text]
    assert any("себя" in a.text for a in alerts)


async def test_env_admin_has_no_remove_button(harness, admin):
    replies = await _open_admins(harness, admin)
    assert "admins:remove:777" not in callbacks_of(replies[0])


# ── reply-клавиатура не должна оставаться после выхода из режима выбора ──

async def _open_picker(harness, admin):
    await _open_admins(harness, admin)
    await harness.send_callback("admins:add", admin)


def _keyboard_removed(replies) -> bool:
    return any(isinstance(r.reply_markup, ReplyKeyboardRemove) for r in replies)


async def test_cancel_command_in_picker_removes_keyboard(harness, admin):
    await _open_picker(harness, admin)
    replies = await harness.send_message("/cancel", admin)
    assert await harness.state_of(admin) is None
    assert _keyboard_removed(replies)


async def test_any_text_in_picker_cancels_and_removes_keyboard(harness, admin):
    await _open_picker(harness, admin)
    replies = await harness.send_message("привет", admin)
    assert await harness.state_of(admin) is None
    assert _keyboard_removed(replies)
    assert "отмен" in replies[0].text.lower()


async def test_other_command_in_picker_removes_keyboard(harness, admin):
    await _open_picker(harness, admin)
    replies = await harness.send_message("/start", admin)
    assert await harness.state_of(admin) is None
    assert _keyboard_removed(replies)
