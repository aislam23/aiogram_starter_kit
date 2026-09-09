"""
Админ по username: человек указывает @username при настройке, бот при первом сообщении
узнаёт его ID и запоминает как администратора.
"""
import pytest

from app.config import Settings, settings
from tests.harness import make_user

# ── настройки ────────────────────────────────────────────────────

def _settings(**env) -> Settings:
    return Settings(_env_file=None, BOT_TOKEN="42:x", POSTGRES_PASSWORD="x", **env)


def test_admin_usernames_parsed_lowercase_without_at():
    s = _settings(ADMIN_USERNAMES='["@Artem", "Other_One"]')
    assert s.admin_usernames == ["artem", "other_one"]


def test_admin_usernames_accept_comma_separated():
    s = _settings(ADMIN_USERNAMES="@artem, other")
    assert s.admin_usernames == ["artem", "other"]


def test_is_admin_username_is_case_insensitive():
    s = _settings(ADMIN_USERNAMES='["artem"]')
    assert s.is_admin_username("ARTEM")
    assert s.is_admin_username("@Artem")
    assert not s.is_admin_username("someone")
    assert not s.is_admin_username(None)


# ── поведение бота ───────────────────────────────────────────────

@pytest.fixture
def admin_by_username(monkeypatch):
    monkeypatch.setattr(settings, "admin_usernames", ["artem"])
    return make_user(user_id=5005, first_name="Артём", username="Artem")


async def test_user_with_admin_username_gets_admin_panel_and_is_remembered(harness, fake_db, admin_by_username):
    replies = await harness.send_message("/admin", admin_by_username)

    assert "Админская панель" in replies[0].text
    assert fake_db.users[5005].is_admin is True
    assert fake_db.users[5005].admin_username == "artem"


async def test_admin_keeps_rights_after_changing_username(harness, fake_db, admin_by_username):
    await harness.send_message("/start", admin_by_username)
    renamed = make_user(user_id=5005, first_name="Артём", username="totally_new_name")

    replies = await harness.send_message("/admin", renamed)

    assert "Админская панель" in replies[0].text


async def test_stranger_who_takes_old_admin_username_is_not_promoted(harness, fake_db, admin_by_username):
    await harness.send_message("/start", admin_by_username)                      # ID 5005 забрал username artem
    await harness.send_message("/start", make_user(user_id=5005, username="new"))  # админ сменил username
    stranger = make_user(user_id=6006, first_name="Чужой", username="artem")       # кто-то занял старый

    replies = await harness.send_message("/admin", stranger)

    assert "нет прав" in replies[0].text
    assert not fake_db.users[6006].is_admin


async def test_regular_user_without_matching_username_is_not_admin(harness, fake_db, admin_by_username):
    replies = await harness.send_message("/admin", make_user(user_id=7, username="nobody"))
    assert "нет прав" in replies[0].text


async def test_admin_by_id_still_works_without_usernames(harness, admin):
    replies = await harness.send_message("/admin", admin)
    assert "Админская панель" in replies[0].text


async def test_is_admin_filter_uses_database_flag(harness, fake_db):
    from app.filters import IsAdmin

    await fake_db.add_user(user_id=8008, username="x")
    await fake_db.set_admin(8008, "x")
    assert await IsAdmin()(_msg(8008), is_admin=True) is True
    assert await IsAdmin()(_msg(8008), is_admin=False) is False
    assert await IsAdmin()(_msg(777)) is True     # без данных middleware — по ID из настроек


def _msg(user_id: int):
    from datetime import UTC, datetime

    from aiogram.types import Chat, Message

    return Message(message_id=1, date=datetime.now(UTC), chat=Chat(id=user_id, type="private"),
                   from_user=make_user(user_id=user_id), text="/x")
