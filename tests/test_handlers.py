"""
Тесты базовых хендлеров: /start, /help, /status, /admin.
Служат и проверкой, и образцом того, как тестировать новые хендлеры.
"""
from tests.harness import buttons_of


async def test_start_greets_user_by_name(harness, user):
    replies = await harness.send_message("/start", user)
    assert len(replies) == 1
    assert "Привет, Тест" in replies[0].text


async def test_start_saves_user_to_database(harness, fake_db, user):
    await harness.send_message("/start", user)
    assert user.id in fake_db.users
    assert fake_db.users[user.id].username == "tester"


async def test_help_lists_commands(harness):
    replies = await harness.send_message("/help")
    assert "/start" in replies[0].text
    assert "/help" in replies[0].text


async def test_status_reports_environment(harness):
    replies = await harness.send_message("/status")
    assert "Статус бота" in replies[0].text


async def test_admin_panel_denied_for_regular_user(harness, user):
    replies = await harness.send_message("/admin", user)
    assert "нет прав" in replies[0].text


async def test_admin_panel_shows_stats_and_menu(harness, admin, fake_db):
    await harness.send_message("/start", admin)
    harness.clear()

    replies = await harness.send_message("/admin", admin)

    assert "Админская панель" in replies[0].text
    assert "Всего пользователей: <b>1</b>" in replies[0].text
    assert "📊 Рассылка" in buttons_of(replies[0])


async def test_admin_broadcast_button_enters_fsm_state(harness, admin):
    await harness.send_callback("admin_broadcast", admin)
    assert await harness.state_of(admin) == "AdminStates:broadcast_message"


async def test_every_message_registers_user_via_middleware(harness, fake_db, user):
    await harness.send_message("любой текст", user)
    assert ("add_user", {"user_id": user.id, "username": "tester"}) in fake_db.calls
