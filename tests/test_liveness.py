"""
Проверка живых пользователей: сервис (sendChatAction-прогон, отмена, flood-wait, планировщик) и экраны админки.
"""
import asyncio
import importlib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendChatAction

from app.handlers.admin import liveness as liveness_handlers
from app.services.liveness import LivenessProgress, LivenessService, liveness
from tests.harness import callbacks_of

# `app.services.liveness` как атрибут пакета — это экземпляр сервиса, модуль берём через importlib
liveness_module = importlib.import_module("app.services.liveness")
_real_sleep = asyncio.sleep


def _method(chat_id: int) -> SendChatAction:
    return SendChatAction(chat_id=chat_id, action="typing")


class ProbeBot:
    """Бот, у которого судьба каждого пользователя задана заранее."""

    def __init__(self, verdicts: dict[int, str]) -> None:
        self.verdicts = verdicts
        self.probed: list[int] = []
        self.messages: list[tuple[int, str]] = []

    async def send_chat_action(self, chat_id: int, action) -> None:
        self.probed.append(chat_id)
        verdict = self.verdicts.get(chat_id, "alive")
        if verdict == "blocked":
            raise TelegramForbiddenError(method=_method(chat_id), message="Forbidden: bot was blocked by the user")
        if verdict == "deactivated":
            raise TelegramForbiddenError(method=_method(chat_id), message="Forbidden: user is deactivated")
        if verdict == "not_found":
            raise TelegramBadRequest(method=_method(chat_id), message="Bad Request: chat not found")
        if verdict == "flood":
            raise TelegramRetryAfter(method=_method(chat_id), message="Too Many Requests", retry_after=1)

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.messages.append((chat_id, text))


async def no_sleep(_seconds: float) -> None:
    await _real_sleep(0)  # уступить event loop, но не ждать


@pytest.fixture
def fresh_liveness():
    """Глобальный сервис общий на процесс — сбрасываем между тестами."""
    liveness._task, liveness.progress, liveness.last_result = None, None, None
    yield liveness
    liveness._task, liveness.progress, liveness.last_result = None, None, None


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(liveness_module.asyncio, "sleep", no_sleep)


# --- сервис -----------------------------------------------------------------


async def test_run_check_marks_blocked_and_deleted(fake_db, fast):
    for uid in (1, 2, 3, 4):
        await fake_db.add_user(uid)
    bot = ProbeBot({2: "blocked", 3: "not_found", 4: "deactivated"})
    service = LivenessService()
    service.configure(bot)  # type: ignore[arg-type]

    result = await service.run_check("manual")

    assert (result.checked, result.alive, result.blocked, result.deleted, result.errors) == (4, 1, 1, 2, 0)
    assert bot.probed == [1, 2, 3, 4]
    assert fake_db.users[1].bot_blocked is False
    assert all(fake_db.users[uid].bot_blocked for uid in (2, 3, 4))
    assert all(fake_db.users[uid].last_liveness_check_at is not None for uid in (1, 2, 3, 4))
    check = fake_db.liveness_checks[0]
    assert (check.trigger, check.checked, check.cancelled) == ("manual", 4, False)
    assert check.finished_at is not None


async def test_run_check_revives_users_marked_blocked_by_mistake(fake_db, fast):
    await fake_db.add_user(1)
    await fake_db.set_bot_blocked(1, True)
    service = LivenessService()
    service.configure(ProbeBot({}))  # type: ignore[arg-type]

    await service.run_check("manual")

    assert fake_db.users[1].bot_blocked is False


async def test_stop_cancels_run_and_marks_journal_cancelled(fake_db, fresh_liveness, monkeypatch):
    for uid in range(1, 51):
        await fake_db.add_user(uid)
    bot = ProbeBot({})
    fresh_liveness.configure(bot)  # type: ignore[arg-type]
    monkeypatch.setattr(liveness_module.settings, "liveness_rate_limit_rps", 1000)

    task = fresh_liveness.start("manual")
    assert task is not None
    assert fresh_liveness.start("manual") is None  # второй прогон параллельно не стартует
    await asyncio.sleep(0.01)
    assert fresh_liveness.stop() is True
    await fresh_liveness.wait(timeout=1)

    assert task.cancelled()
    result = fresh_liveness.last_result
    assert result is not None and 0 < result.checked < 50
    check = fake_db.liveness_checks[0]
    assert check.cancelled is True and check.finished_at is not None
    assert not fresh_liveness.is_running()


async def test_sustained_flood_wait_aborts_run(fake_db, fast):
    for uid in range(1, 11):
        await fake_db.add_user(uid)
    service = LivenessService()
    service.configure(ProbeBot({uid: "flood" for uid in range(1, 11)}))  # type: ignore[arg-type]

    result = await service.run_check("manual")

    assert result.checked < 10, "после серии flood-wait прогон должен прерваться"
    assert result.errors == result.checked
    assert fake_db.liveness_checks[0].cancelled is True


async def test_scheduler_skips_if_recent_run_completed(fake_db, fresh_liveness, monkeypatch):
    monkeypatch.setattr(liveness_module, "NIGHT_WINDOW", range(0, 24))
    check_id = await fake_db.create_liveness_check("scheduled")
    await fake_db.update_liveness_check(check_id, checked=1, alive=1, blocked=0, deleted=0, errors=0, finished=True)
    bot = ProbeBot({})
    fresh_liveness.configure(bot)  # type: ignore[arg-type]

    await fresh_liveness._maybe_run_scheduled()

    assert bot.probed == []


async def test_scheduler_runs_when_due_and_notifies_admins(fake_db, fresh_liveness, fast, monkeypatch, admin):
    monkeypatch.setattr(liveness_module, "NIGHT_WINDOW", range(0, 24))
    await fake_db.add_user(admin.id)
    await fake_db.add_user(5)
    # Старый прогон — старше интервала
    check_id = await fake_db.create_liveness_check("scheduled")
    await fake_db.update_liveness_check(check_id, checked=1, alive=1, blocked=0, deleted=0, errors=0, finished=True)
    fake_db.liveness_checks[0].finished_at = datetime.now(UTC) - timedelta(days=30)
    bot = ProbeBot({5: "blocked"})
    fresh_liveness.configure(bot)  # type: ignore[arg-type]

    await fresh_liveness._maybe_run_scheduled()

    assert sorted(bot.probed) == [5, admin.id]
    assert [chat_id for chat_id, _ in bot.messages] == [admin.id]
    assert "по расписанию" in bot.messages[0][1]
    assert "Заблокировали бота: <b>1</b>" in bot.messages[0][1]


async def test_scheduler_outside_night_window_does_nothing(fake_db, fresh_liveness, monkeypatch):
    monkeypatch.setattr(liveness_module, "NIGHT_WINDOW", range(0, 0))
    bot = ProbeBot({})
    fresh_liveness.configure(bot)  # type: ignore[arg-type]

    await fresh_liveness._maybe_run_scheduled()

    assert bot.probed == []


async def test_scheduler_disabled_by_zero_interval(fake_db, fresh_liveness, monkeypatch):
    monkeypatch.setattr(liveness_module, "NIGHT_WINDOW", range(0, 24))
    monkeypatch.setattr(liveness_module.settings, "liveness_check_interval_days", 0)
    bot = ProbeBot({})
    fresh_liveness.configure(bot)  # type: ignore[arg-type]

    await fresh_liveness._maybe_run_scheduled()

    assert bot.probed == []


# --- экраны админки ---------------------------------------------------------


async def _wait_watchers() -> None:
    await liveness.wait(timeout=1)
    if liveness_handlers._watchers:
        await asyncio.gather(*list(liveness_handlers._watchers))


async def test_liveness_menu_shows_confirmation(harness, fake_db, admin, user, fresh_liveness):
    await harness.send_message("/start", admin)
    await harness.send_message("/start", user)

    replies = await harness.send_callback("admin_liveness", admin)

    assert "Будет проверено ~2 пользователей" in replies[-1].text
    assert "liveness:confirm" in callbacks_of(replies[-1])


async def test_liveness_menu_denied_for_regular_user(harness, user, fresh_liveness):
    replies = await harness.send_callback("admin_liveness", user)
    assert replies == []


async def test_liveness_confirm_runs_check_and_reports(harness, fake_db, admin, user, fresh_liveness, fast):
    await harness.send_message("/start", admin)
    await harness.send_message("/start", user)
    forbidden = ProbeBot({user.id: "blocked"})
    # Прогон ходит в Telegram через bot.send_chat_action — подменяем только его
    with patch.object(type(harness.bot), "send_chat_action", forbidden.send_chat_action, create=True):
        harness.clear()
        await harness.send_callback("liveness:confirm", admin)
        await _wait_watchers()

    texts = [c.text for c in harness.sent]
    assert any("Запускаю" in t for t in texts)
    assert "Проверка живых завершена" in texts[-1]
    assert "Заблокировали бота: <b>1</b>" in texts[-1]
    assert "liveness:back" in callbacks_of(harness.sent[-1])
    assert fake_db.users[user.id].bot_blocked is True
    assert not liveness.is_running()


async def test_liveness_stop_without_run(harness, admin, fresh_liveness):
    from aiogram.methods import AnswerCallbackQuery

    await harness.send_callback("liveness:stop", admin)

    answers = [c for c in harness.calls if isinstance(c, AnswerCallbackQuery)]
    assert answers and "не идёт" in (answers[-1].text or "")


async def test_liveness_back_returns_to_panel(harness, admin, fresh_liveness):
    await harness.send_message("/start", admin)

    replies = await harness.send_callback("liveness:back", admin)

    assert "Админская панель" in replies[-1].text
    assert "admin_liveness" in callbacks_of(replies[-1])


def test_progress_percent_and_elapsed():
    progress = LivenessProgress(total=200, checked=50)
    assert progress.percent == 25
    assert LivenessProgress(total=0).percent == 100
    assert progress.elapsed.total_seconds() >= 0
