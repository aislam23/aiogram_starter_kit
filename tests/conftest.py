"""
Общие фикстуры. Переменные окружения задаются ДО импорта app.*, чтобы Settings() не требовал .env.
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

os.environ.setdefault("BOT_TOKEN", "42:TEST_TOKEN_FOR_TESTS_ONLY")
os.environ.setdefault("BOT_USERNAME", "test_bot")
os.environ.setdefault("ADMIN_USER_IDS", "[777]")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("EXAMPLE_HANDLERS", "true")
os.environ.setdefault("LOG_FILE", "")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import UTC

from app.database import db  # noqa: E402
from app.database.models import BotStats, User  # noqa: E402
from tests.harness import BotHarness, make_user  # noqa: E402

ADMIN_ID = 777


class FakeDb:
    """Заглушка базы данных: хранит пользователей в памяти и записывает вызовы."""

    def __init__(self) -> None:
        self.users: Dict[int, User] = {}
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    async def add_user(self, user_id: int, username=None, first_name=None, last_name=None) -> User:
        self.calls.append(("add_user", {"user_id": user_id, "username": username}))
        user = self.users.get(user_id) or User(id=user_id)
        user.username, user.first_name, user.last_name, user.is_active = username, first_name, last_name, True
        self.users[user_id] = user
        return user

    async def get_user(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)

    async def get_all_users(self) -> List[User]:
        return list(self.users.values())

    async def get_active_users(self) -> List[User]:
        return [u for u in self.users.values() if u.is_active]

    async def get_users_count(self) -> int:
        return len(self.users)

    async def get_active_users_count(self) -> int:
        return len(await self.get_active_users())

    async def get_bot_stats(self) -> Optional[BotStats]:
        from datetime import datetime
        return BotStats(total_users=len(self.users), active_users=len(self.users),
                        last_restart=datetime.now(UTC), status="active")

    async def update_bot_stats(self) -> BotStats:
        return await self.get_bot_stats()


@pytest.fixture
def fake_db(monkeypatch) -> FakeDb:
    """Подменяет методы синглтона `db` на заглушку в памяти."""
    fake = FakeDb()
    for name in ("add_user", "get_user", "get_all_users", "get_active_users",
                 "get_users_count", "get_active_users_count", "get_bot_stats", "update_bot_stats"):
        monkeypatch.setattr(db, name, getattr(fake, name))
    return fake


@pytest.fixture(scope="session")
def _harness_singleton() -> BotHarness:
    # Роутеры aiogram — синглтоны уровня модуля, их нельзя подключить ко второму Dispatcher.
    # Поэтому Dispatcher один на всю сессию, а между тестами сбрасываем состояние.
    return BotHarness()


@pytest.fixture
def harness(fake_db, _harness_singleton) -> BotHarness:
    """Dispatcher + Bot с фейковой сессией. База уже подменена, состояние чистое."""
    _harness_singleton.reset()
    return _harness_singleton


@pytest.fixture
def admin():
    return make_user(user_id=ADMIN_ID, first_name="Админ", username="admin")


@pytest.fixture
def user():
    return make_user(user_id=1, first_name="Тест", username="tester")
