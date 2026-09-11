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

from datetime import UTC, datetime

from app.database import db  # noqa: E402
from app.database.models import BotStats, LivenessCheck, User  # noqa: E402
from tests.harness import BotHarness, make_user  # noqa: E402

ADMIN_ID = 777


class FakeDb:
    """Заглушка базы данных: хранит пользователей в памяти и записывает вызовы."""

    def __init__(self) -> None:
        self.users: Dict[int, User] = {}
        self.liveness_checks: List[LivenessCheck] = []
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    async def add_user(self, user_id: int, username=None, first_name=None, last_name=None) -> User:
        self.calls.append(("add_user", {"user_id": user_id, "username": username}))
        user = self.users.get(user_id) or User(
            id=user_id, is_admin=False, admin_username=None, bot_blocked=False, bot_blocked_at=None
        )
        user.username, user.first_name, user.last_name, user.is_active = username, first_name, last_name, True
        # Написал боту — значит, не блокирует его
        user.bot_blocked, user.bot_blocked_at = False, None
        self.users[user_id] = user
        return user

    async def set_bot_blocked(self, user_id: int, blocked: bool) -> None:
        self.calls.append(("set_bot_blocked", {"user_id": user_id, "blocked": blocked}))
        user = self.users.get(user_id)
        if user:
            user.bot_blocked = blocked
            user.bot_blocked_at = (user.bot_blocked_at or datetime.now(UTC)) if blocked else None

    async def get_alive_users(self) -> List[User]:
        return [u for u in self.users.values() if u.is_active and not u.bot_blocked]

    async def get_alive_users_count(self) -> int:
        return len(await self.get_alive_users())

    async def get_blocked_users_count(self) -> int:
        return len([u for u in self.users.values() if u.bot_blocked])

    # --- проверка живых (LivenessService) ---

    async def count_liveness_users(self) -> int:
        return len(await self.get_active_users())

    async def get_liveness_user_ids(self, after_id: int, limit: int) -> List[int]:
        ids = sorted(u.id for u in self.users.values() if u.is_active and u.id > after_id)
        return ids[:limit]

    async def apply_liveness_results(self, checked_ids, alive_ids, blocked_ids) -> None:
        self.calls.append(("apply_liveness_results", {"checked": list(checked_ids), "alive": list(alive_ids),
                                                      "blocked": list(blocked_ids)}))
        for uid in checked_ids:
            if uid in self.users:
                self.users[uid].last_liveness_check_at = datetime.now(UTC)
        for uid in alive_ids:
            await self.set_bot_blocked(uid, False)
        for uid in blocked_ids:
            await self.set_bot_blocked(uid, True)

    async def create_liveness_check(self, trigger: str) -> int:
        check = LivenessCheck(id=len(self.liveness_checks) + 1, trigger=trigger, started_at=datetime.now(UTC),
                              checked=0, alive=0, blocked=0, deleted=0, errors=0, cancelled=False)
        self.liveness_checks.append(check)
        return check.id

    async def update_liveness_check(self, check_id: int, *, checked, alive, blocked, deleted, errors,
                                    finished: bool, cancelled: bool = False) -> None:
        check = self.liveness_checks[check_id - 1]
        check.checked, check.alive, check.blocked, check.deleted, check.errors = checked, alive, blocked, deleted, errors
        if finished:
            check.finished_at, check.cancelled = datetime.now(UTC), cancelled

    async def get_last_completed_liveness_check(self) -> Optional[LivenessCheck]:
        done = [c for c in self.liveness_checks if c.finished_at is not None and not c.cancelled]
        return max(done, key=lambda c: c.finished_at) if done else None

    async def set_admin(self, user_id: int, claimed_username: Optional[str] = None) -> None:
        user = self.users.get(user_id)
        if user:
            user.is_admin = True
            if claimed_username:
                user.admin_username = claimed_username.lower().lstrip("@")

    async def remove_admin(self, user_id: int) -> None:
        user = self.users.get(user_id)
        if user:
            user.is_admin, user.admin_username = False, None

    async def get_admins(self) -> List[User]:
        return sorted((u for u in self.users.values() if u.is_admin), key=lambda u: u.id)

    async def get_admin_by_username(self, username: str) -> Optional[User]:
        wanted = username.lower().lstrip("@")
        return next((u for u in self.users.values() if u.is_admin and u.admin_username == wanted), None)

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
        return BotStats(total_users=len(self.users), active_users=len(self.users),
                        last_restart=datetime.now(UTC), status="active")

    async def update_bot_stats(self) -> BotStats:
        return await self.get_bot_stats()


@pytest.fixture
def fake_db(monkeypatch) -> FakeDb:
    """Подменяет методы синглтона `db` на заглушку в памяти."""
    fake = FakeDb()
    for name in ("add_user", "get_user", "get_all_users", "get_active_users",
                 "get_users_count", "get_active_users_count", "get_bot_stats", "update_bot_stats",
                 "set_admin", "get_admin_by_username", "remove_admin", "get_admins",
                 "set_bot_blocked", "get_alive_users", "get_alive_users_count", "get_blocked_users_count",
                 "count_liveness_users", "get_liveness_user_ids", "apply_liveness_results",
                 "create_liveness_check", "update_liveness_check", "get_last_completed_liveness_check"):
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
