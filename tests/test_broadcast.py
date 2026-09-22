"""
Тесты рассылки: троттлинг прогресса, отправка с ровным темпом, flood-wait, чекпоинты,
остановка и возобновление, экраны админки.

Прогресс рассылки редактирует одно сообщение тысячи раз подряд — без троттлинга
Telegram отвечает flood control, экран замирает, а финальный отчёт не доходит.
"""
import asyncio
import importlib
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import EditMessageText, SendMessage, SendPhoto, SendSticker
from aiogram.types import Chat, Message, MessageEntity, PhotoSize, Sticker, User

from app.keyboards import AdminKeyboards
from app.services.broadcast import (
    MAX_RETRIES,
    BroadcastProgress,
    BroadcastService,
    ProgressReporter,
    broadcast,
    build_send_method,
    format_broadcast_result,
)
from app.services.liveness import LivenessProgress, liveness

broadcast_module = importlib.import_module("app.services.broadcast")
_real_sleep = asyncio.sleep


def retry_after(seconds: int) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=SendMessage(chat_id=1, text="x"), message="Flood control exceeded", retry_after=seconds
    )


def forbidden() -> TelegramForbiddenError:
    return TelegramForbiddenError(method=SendMessage(chat_id=1, text="x"), message="Forbidden: bot was blocked by the user")


def bad_request(text: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=SendMessage(chat_id=1, text="x"), message=f"Bad Request: {text}")


_ADMIN = User(id=777, is_bot=False, first_name="Админ")
_CHAT = Chat(id=777, type="private")


def text_message(text: str = "привет", entities=None) -> Message:
    return Message(message_id=1, date=datetime.now(UTC), chat=_CHAT, from_user=_ADMIN, text=text, entities=entities)


def bold_message() -> Message:
    """«жирный и <» с bold на первом слове: html_text даёт <b>жирный</b> и &lt;"""
    return text_message("жирный и <", entities=[MessageEntity(type="bold", offset=0, length=6)])


def photo_message(caption: str = "подпись") -> Message:
    photo = PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)
    return Message(message_id=1, date=datetime.now(UTC), chat=_CHAT, from_user=_ADMIN, photo=[photo], caption=caption)


def sticker_message() -> Message:
    sticker = Sticker(file_id="s", file_unique_id="su", type="regular", width=1, height=1, is_animated=False, is_video=False)
    return Message(message_id=1, date=datetime.now(UTC), chat=_CHAT, from_user=_ADMIN, sticker=sticker)


class FakeBot:
    """Записывает отправленные методы; по сценарию бросает исключения на заданных chat_id."""

    def __init__(self, fail: dict[int, list[Exception]] | None = None) -> None:
        self.methods: list = []
        self.fail = fail or {}  # chat_id -> очередь исключений, по одному на попытку

    async def __call__(self, method):
        self.methods.append(method)
        queue = self.fail.get(method.chat_id)
        if queue:
            raise queue.pop(0)
        return None

    @property
    def chat_ids(self) -> list[int]:
        return [m.chat_id for m in self.methods]


def _service(bot) -> BroadcastService:
    service = BroadcastService()
    service.configure(bot)
    return service


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    """asyncio.sleep в модуле рассылки не ждёт, но записывает запрошенные интервалы."""
    calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        calls.append(seconds)
        await _real_sleep(0)  # уступить event loop

    monkeypatch.setattr(broadcast_module.asyncio, "sleep", fake_sleep)
    return calls


@pytest.fixture
def fresh_broadcast():
    """Глобальный сервис общий на процесс — сбрасываем между тестами."""
    def _reset() -> None:
        broadcast._task, broadcast.progress, broadcast.last_result = None, None, None
        broadcast._stop_requested = False

    _reset()
    yield broadcast
    _reset()


async def _drain_watchers() -> None:
    """Дождаться наблюдателей (они дописывают итог после задачи рассылки)."""
    for watcher in list(broadcast_module._watchers):
        await watcher


async def no_sleep(_seconds: float) -> None:
    pass


class FakeProgressMessage:
    """Сообщение прогресса: считает правки и умеет падать flood-wait заданное число раз."""

    def __init__(self, fail_edits: int = 0) -> None:
        self.edits: list[str] = []
        self.answers: list[str] = []
        self.fail_edits = fail_edits

    async def edit_text(self, text: str, reply_markup=None):
        if self.fail_edits > 0:
            self.fail_edits -= 1
            raise retry_after(2)
        self.edits.append(text)

    async def answer(self, text: str, reply_markup=None):
        self.answers.append(text)


# --- ProgressReporter -------------------------------------------------------


async def test_progress_reporter_throttles_edits():
    message = FakeProgressMessage()
    reporter = ProgressReporter(message, min_interval=5)

    results = [await reporter.update(f"шаг {i}") for i in range(100)]

    assert sum(results) == 1
    assert message.edits == ["шаг 0"]


async def test_progress_reporter_edits_again_after_interval():
    message = FakeProgressMessage()
    reporter = ProgressReporter(message, min_interval=5)
    await reporter.update("первый")

    reporter._last_edit_at -= 10  # прошло больше min_interval

    assert await reporter.update("второй") is True
    assert message.edits[-1] == "второй"


async def test_progress_reporter_stays_silent_during_flood_wait():
    message = FakeProgressMessage(fail_edits=1)
    reporter = ProgressReporter(message, min_interval=0)

    assert await reporter.update("a") is False  # получили flood-wait
    assert await reporter.update("b") is False  # молчим, API не трогаем
    assert message.edits == []

    reporter._muted_until = 0  # flood-wait истёк
    assert await reporter.update("c") is True
    assert message.edits == ["c"]


async def test_progress_reporter_finish_waits_out_flood_wait():
    message = FakeProgressMessage(fail_edits=2)
    reporter = ProgressReporter(message)

    with patch("app.services.broadcast.asyncio.sleep", no_sleep):
        await reporter.finish("итог")

    assert message.edits == ["итог"]
    assert message.answers == []


async def test_progress_reporter_finish_falls_back_to_new_message():
    message = FakeProgressMessage(fail_edits=99)
    reporter = ProgressReporter(message)

    with patch("app.services.broadcast.asyncio.sleep", no_sleep):
        await reporter.finish("итог")

    assert message.edits == []
    assert message.answers == ["итог"]


# --- build_send_method: Send* по типу сообщения, текст как HTML -------------


def test_build_send_method_text_uses_html_without_entities():
    method = build_send_method(bold_message(), chat_id=5, keyboard=None)

    assert isinstance(method, SendMessage)
    assert method.chat_id == 5
    assert method.text == "<b>жирный</b> и &lt;"
    assert method.entities is None
    assert method.parse_mode == "HTML"


def test_build_send_method_caption_and_keyboard():
    keyboard = AdminKeyboards.create_custom_button("Сайт", "https://example.com")

    method = build_send_method(photo_message(), chat_id=5, keyboard=keyboard)

    assert isinstance(method, SendPhoto)
    assert method.photo == "f"
    assert (method.caption, method.caption_entities, method.parse_mode) == ("подпись", None, "HTML")
    assert method.reply_markup is keyboard


def test_build_send_method_leaves_sticker_untouched():
    method = build_send_method(sticker_message(), chat_id=5, keyboard=None)

    assert isinstance(method, SendSticker)
    assert method.sticker == "s"


def test_build_send_method_works_after_json_round_trip():
    restored = Message.model_validate_json(bold_message().model_dump_json())

    assert build_send_method(restored, chat_id=1, keyboard=None).text == "<b>жирный</b> и &lt;"


def test_build_send_method_rejects_empty_message():
    empty = Message(message_id=1, date=datetime.now(UTC), chat=_CHAT, from_user=_ADMIN)

    with pytest.raises(TypeError):
        build_send_method(empty, chat_id=1, keyboard=None)


# --- _send: одна отправка с вердиктом ----------------------------------------


async def test_send_waits_full_retry_after_and_retries(fake_db, sleeps):
    bot = FakeBot({42: [retry_after(7)]})

    verdict = await _service(bot)._send(42, text_message(), None)

    assert verdict == "sent"
    assert sleeps == [7]  # без урезания: меньше ждать — получить следующий 429
    assert bot.chat_ids == [42, 42]


async def test_send_gives_up_after_max_retries(fake_db, sleeps):
    bot = FakeBot({42: [retry_after(1)] * MAX_RETRIES})
    service = _service(bot)

    assert await service._send(42, text_message(), None) == "failed"
    assert len(bot.chat_ids) == MAX_RETRIES
    assert sleeps == [1] * MAX_RETRIES
    assert service._error_kinds["RetryAfter:exhausted"] == 1


async def test_send_marks_blocked_on_forbidden(fake_db, sleeps):
    await fake_db.add_user(42)
    bot = FakeBot({42: [forbidden()]})

    assert await _service(bot)._send(42, text_message(), None) == "blocked"
    assert fake_db.users[42].bot_blocked is True


async def test_send_treats_deleted_account_as_blocked(fake_db, sleeps):
    await fake_db.add_user(42)
    bot = FakeBot({42: [bad_request("chat not found")]})

    assert await _service(bot)._send(42, text_message(), None) == "blocked"
    assert fake_db.users[42].bot_blocked is True


async def test_send_counts_other_bad_request_as_failed(fake_db, sleeps):
    bot = FakeBot({42: [bad_request("wrong file identifier")]})
    service = _service(bot)

    assert await service._send(42, text_message(), None) == "failed"
    assert list(service._error_kinds) == ["BadRequest:Bad Request: wrong file identifier"]


# --- run: ровный темп, курсор, чекпоинты, статусы ----------------------------


async def _new_broadcast(fake_db, message: Message | None = None, total: int | None = None, **button) -> int:
    message = message or text_message()
    return await fake_db.create_broadcast(
        created_by=777, content=message.model_dump_json(), button_text=button.get("button_text"),
        button_url=button.get("button_url"), total=len(fake_db.users) if total is None else total,
    )


async def test_run_paces_sends_evenly(fake_db, sleeps, monkeypatch):
    for uid in range(1, 6):
        await fake_db.add_user(uid)
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 10)
    bot = FakeBot()
    bid = await _new_broadcast(fake_db)

    result = await _service(bot).run(bid)

    assert bot.chat_ids == [1, 2, 3, 4, 5]
    assert (result.status, result.sent, result.processed) == ("done", 5, 5)
    # sleep не ждёт, monotonic почти не растёт → аргументы кумулятивны (0, 0.1, 0.2…); ровный темп = равные разности
    assert len(sleeps) == 5
    gaps = [b - a for a, b in zip(sleeps, sleeps[1:], strict=False)]  # ruff B905
    assert all(abs(gap - 0.1) < 0.02 for gap in gaps), sleeps


async def test_run_checkpoints_cursor_every_n_sends(fake_db, sleeps):
    n = broadcast_module.CHECKPOINT_EVERY * 2 + 20
    for uid in range(1, n + 1):
        await fake_db.add_user(uid)
    bid = await _new_broadcast(fake_db)

    await _service(FakeBot()).run(bid)

    updates = [c[1] for c in fake_db.calls if c[0] == "update_broadcast"]
    assert [u["last_user_id"] for u in updates] == [50, 100, n]
    assert [u["status"] for u in updates] == [None, None, "done"]
    row = fake_db.broadcasts[bid]
    assert (row.status, row.sent, row.last_user_id) == ("done", n, n)
    assert row.finished_at is not None


async def test_run_resumes_from_cursor(fake_db, sleeps):
    for uid in (1, 2, 3, 4, 5):
        await fake_db.add_user(uid)
    bid = await _new_broadcast(fake_db)
    await fake_db.update_broadcast(bid, last_user_id=3, sent=3, failed=0, blocked=0)
    bot = FakeBot()

    result = await _service(bot).run(bid)

    assert bot.chat_ids == [4, 5]
    assert (result.sent, result.processed, result.status) == (5, 5, "done")


async def test_run_skips_users_who_blocked_bot(fake_db, sleeps):
    for uid in (1, 2, 3):
        await fake_db.add_user(uid)
    await fake_db.set_bot_blocked(2, True)
    bid = await _new_broadcast(fake_db, total=2)
    bot = FakeBot()

    await _service(bot).run(bid)

    assert bot.chat_ids == [1, 3]


async def test_run_sends_button_from_row(fake_db, sleeps):
    await fake_db.add_user(1)
    bid = await _new_broadcast(fake_db, button_text="Сайт", button_url="https://example.com")
    bot = FakeBot()

    await _service(bot).run(bid)

    button = bot.methods[0].reply_markup.inline_keyboard[0][0]
    assert (button.text, button.url) == ("Сайт", "https://example.com")


async def test_run_reports_progress_immediately_then_throttled(fake_db, sleeps):
    for uid in (1, 2, 3):
        await fake_db.add_user(uid)
    bid = await _new_broadcast(fake_db)
    seen: list[int] = []

    async def on_progress(progress) -> None:
        seen.append(progress.processed)

    await _service(FakeBot()).run(bid, on_progress)

    assert seen == [1]  # первый отчёт сразу, следующие не чаще PROGRESS_EVERY_SECONDS


async def test_run_fails_when_content_is_invalid(fake_db, sleeps):
    from pydantic import ValidationError

    await fake_db.add_user(1)
    bid = await fake_db.create_broadcast(created_by=777, content="{not json", button_text=None, button_url=None, total=1)
    service = _service(FakeBot())

    with pytest.raises(ValidationError):
        await service.run(bid)

    row = fake_db.broadcasts[bid]
    assert row.status == "failed" and row.finished_at is not None  # иначе resume_pending поднимал бы её вечно
    assert service.last_result.status == "failed"
    assert not service.is_running()


async def test_run_fails_fast_on_unsupported_message_type(fake_db, sleeps):
    for uid in (1, 2, 3):
        await fake_db.add_user(uid)
    empty = Message(message_id=1, date=datetime.now(UTC), chat=_CHAT, from_user=_ADMIN)
    bid = await _new_broadcast(fake_db, message=empty)
    bot = FakeBot()

    with pytest.raises(TypeError):
        await _service(bot).run(bid)

    assert bot.chat_ids == []  # не 3 «failed» по одному, а сразу стоп
    assert fake_db.broadcasts[bid].status == "failed"


async def test_run_refuses_finished_broadcast(fake_db, sleeps):
    bid = await _new_broadcast(fake_db)
    await fake_db.update_broadcast(bid, last_user_id=0, sent=0, failed=0, blocked=0, status="done")

    with pytest.raises(RuntimeError):
        await _service(FakeBot()).run(bid)


# --- start/stop/wait, shutdown, resume_pending ------------------------------


async def test_stop_marks_stopped_and_keeps_cursor(fake_db, fresh_broadcast, monkeypatch):
    for uid in range(1, 51):
        await fake_db.add_user(uid)
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 1000)  # 1 мс на получателя, реальный sleep
    bot = FakeBot()
    fresh_broadcast.configure(bot)
    bid = await _new_broadcast(fake_db)

    task = fresh_broadcast.start(bid)
    assert task is not None
    assert fresh_broadcast.start(bid) is None  # вторая параллельно не стартует
    await _real_sleep(0.01)
    assert fresh_broadcast.stop() is True
    await fresh_broadcast.wait(timeout=1)

    assert task.cancelled()
    result = fresh_broadcast.last_result
    assert result.status == "stopped" and 0 < result.processed < 50
    row = fake_db.broadcasts[bid]
    assert row.status == "stopped" and row.finished_at is not None
    assert row.last_user_id == bot.chat_ids[-1]  # курсор — последний обработанный
    assert not fresh_broadcast.is_running()
    assert fresh_broadcast.stop() is False


async def test_shutdown_keeps_broadcast_running_in_db(fake_db, fresh_broadcast, monkeypatch):
    for uid in range(1, 51):
        await fake_db.add_user(uid)
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 1000)
    fresh_broadcast.configure(FakeBot())
    bid = await _new_broadcast(fake_db)

    fresh_broadcast.start(bid)
    await _real_sleep(0.01)
    assert fresh_broadcast.stop_for_shutdown() is True
    await fresh_broadcast.wait(timeout=1)

    row = fake_db.broadcasts[bid]
    assert row.status == "running" and row.finished_at is None  # возобновится после рестарта
    assert 0 < row.last_user_id < 50
    assert fresh_broadcast.last_result.status == "running"


async def test_resume_pending_continues_and_notifies_admins(fake_db, fresh_broadcast, sleeps, monkeypatch):
    for uid in (1, 2, 3, 4, 5):
        await fake_db.add_user(uid)
    bid = await _new_broadcast(fake_db)
    await fake_db.update_broadcast(bid, last_user_id=3, sent=3, failed=0, blocked=0)
    bot = FakeBot()
    fresh_broadcast.configure(bot)
    notified: list[str] = []

    async def fake_notify(_bot, text: str) -> None:
        notified.append(text)

    monkeypatch.setattr(broadcast_module, "notify_admins", fake_notify)

    await fresh_broadcast.resume_pending()
    await fresh_broadcast.wait(timeout=1)
    await _drain_watchers()

    assert bot.chat_ids == [4, 5]
    assert fake_db.broadcasts[bid].status == "done"
    assert len(notified) == 1 and "Рассылка завершена" in notified[0] and "<b>5</b>" in notified[0]


async def test_resume_pending_without_running_broadcast_does_nothing(fake_db, fresh_broadcast):
    fresh_broadcast.configure(FakeBot())

    await fresh_broadcast.resume_pending()

    assert not fresh_broadcast.is_running()


async def test_resume_pending_stays_silent_if_interrupted_again(fake_db, fresh_broadcast, monkeypatch):
    for uid in range(1, 51):
        await fake_db.add_user(uid)
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 1000)
    await _new_broadcast(fake_db)
    fresh_broadcast.configure(FakeBot())
    notified: list[str] = []

    async def fake_notify(_bot, text: str) -> None:
        notified.append(text)

    monkeypatch.setattr(broadcast_module, "notify_admins", fake_notify)

    await fresh_broadcast.resume_pending()
    await _real_sleep(0.01)
    fresh_broadcast.stop_for_shutdown()
    await fresh_broadcast.wait(timeout=1)
    await _drain_watchers()

    assert notified == []


async def test_broadcast_refuses_while_liveness_runs(fake_db, fresh_broadcast):
    liveness.progress = LivenessProgress(total=1)  # эмулируем идущий прогон
    try:
        assert fresh_broadcast.start(1) is None
    finally:
        liveness.progress = None


async def test_liveness_refuses_while_broadcast_runs(fake_db, fresh_broadcast):
    fresh_broadcast.progress = BroadcastProgress(broadcast_id=1, total=1)

    assert liveness.start("manual") is None


# --- тексты ------------------------------------------------------------------


def test_format_result_for_stopped_broadcast():
    result = BroadcastProgress(broadcast_id=1, total=100, sent=40, failed=2, blocked=3, status="stopped")

    text = format_broadcast_result(result)

    assert text.startswith("⏹ <b>Рассылка остановлена</b>")
    assert "Остановлена на <b>45</b> из 100" in text
    assert "Доставлено: <b>40</b>" in text and "Успешность: <b>40%</b>" in text


# --- confirm_broadcast: FSM очищается при любом исходе ----------------------


async def _arm_confirm_state(harness, admin):
    """Админ уже отправил контент рассылки и видит кнопку подтверждения."""
    await harness.send_message("/start", admin)
    await harness.send_callback("admin_broadcast", admin)
    await harness.send_message("Текст рассылки", admin)
    harness.clear()


async def test_confirm_broadcast_reports_result_and_clears_state(harness, admin, monkeypatch):
    await _arm_confirm_state(harness, admin)

    async def fake_send_broadcast(self, **kwargs):
        return {"total": 10, "sent": 9, "failed": 0, "blocked": 1}

    monkeypatch.setattr(BroadcastService, "send_broadcast", fake_send_broadcast)

    replies = await harness.send_callback("broadcast_confirm_yes", admin)

    assert "Рассылка завершена" in replies[-1].text
    assert "Успешно доставлено: <b>9</b>" in replies[-1].text
    assert await harness.state_of(admin) is None


async def test_confirm_broadcast_clears_state_even_if_broadcast_fails(harness, admin, monkeypatch):
    await _arm_confirm_state(harness, admin)

    async def failing_send_broadcast(self, **kwargs):
        raise RuntimeError("упало")

    monkeypatch.setattr(BroadcastService, "send_broadcast", failing_send_broadcast)

    replies = await harness.send_callback("broadcast_confirm_yes", admin)

    assert "Ошибка при рассылке" in replies[-1].text
    assert await harness.state_of(admin) is None


async def test_confirm_broadcast_answers_callback_before_sending(harness, admin, monkeypatch):
    """Рассылка идёт долго, а callback query протухает — отвечать надо до старта."""
    from aiogram.methods import AnswerCallbackQuery

    await _arm_confirm_state(harness, admin)
    order: list[str] = []

    async def fake_send_broadcast(self, **kwargs):
        order.append("broadcast")
        return {"total": 0, "sent": 0, "failed": 0, "blocked": 0}

    monkeypatch.setattr(BroadcastService, "send_broadcast", fake_send_broadcast)

    await harness.send_callback("broadcast_confirm_yes", admin)

    answered_at = next(i for i, c in enumerate(harness.calls) if isinstance(c, AnswerCallbackQuery))
    started_at = next(i for i, c in enumerate(harness.calls) if isinstance(c, EditMessageText) and "запущена" in (c.text or ""))
    assert answered_at < started_at, "callback.answer() должен идти до запуска рассылки"
    assert order == ["broadcast"]


# --- FakeDb: рассылки и курсор живых --------------------------------------


async def test_fake_db_alive_user_ids_cursor_skips_blocked(fake_db):
    for uid in (1, 2, 3, 4):
        await fake_db.add_user(uid)
    await fake_db.set_bot_blocked(2, True)

    assert await fake_db.get_alive_user_ids(0, 2) == [1, 3]
    assert await fake_db.get_alive_user_ids(3, 2) == [4]
    assert await fake_db.get_alive_user_ids(4, 2) == []


async def test_fake_db_broadcast_lifecycle(fake_db):
    bid = await fake_db.create_broadcast(created_by=777, content="{}", button_text=None, button_url=None, total=5)

    row = await fake_db.get_running_broadcast()
    assert row is not None and row.id == bid and row.status == "running" and row.finished_at is None

    await fake_db.update_broadcast(bid, last_user_id=3, sent=3, failed=0, blocked=0)
    assert (await fake_db.get_broadcast(bid)).last_user_id == 3
    assert (await fake_db.get_running_broadcast()).id == bid  # без статуса — всё ещё running

    await fake_db.update_broadcast(bid, last_user_id=5, sent=4, failed=0, blocked=1, status="done")
    assert await fake_db.get_running_broadcast() is None
    last = await fake_db.get_last_broadcast()
    assert (last.status, last.sent, last.blocked) == ("done", 4, 1) and last.finished_at is not None
