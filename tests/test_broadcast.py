"""
Тесты рассылки: троттлинг прогресса, устойчивость к flood-wait, очистка FSM.

Прогресс рассылки редактирует одно сообщение тысячи раз подряд — без троттлинга
Telegram отвечает flood control, экран замирает, а финальный отчёт не доходит.
"""
from unittest.mock import patch

from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import EditMessageText, SendMessage

from app.services.broadcast import BroadcastService, ProgressReporter


def retry_after(seconds: int) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=SendMessage(chat_id=1, text="x"), message="Flood control exceeded", retry_after=seconds
    )


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


async def no_sleep(_seconds: float) -> None:
    pass


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


# --- BroadcastService: повтор при flood-wait --------------------------------


class FakeBot:
    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.sent: list[int] = []

    async def send_message(self, chat_id: int, **kwargs):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise retry_after(3)
        self.sent.append(chat_id)


class FakeTextMessage:
    text = "привет"
    html_text = "привет"
    photo = video = document = audio = voice = video_note = animation = sticker = None


async def test_send_single_message_retries_after_flood_wait():
    bot = FakeBot(fail_times=1)
    service = BroadcastService(bot)  # type: ignore[arg-type]

    with patch("app.services.broadcast.asyncio.sleep", no_sleep):
        ok = await service._send_single_message(user_id=42, message=FakeTextMessage())  # type: ignore[arg-type]

    assert ok is True
    assert bot.sent == [42]


async def test_send_single_message_gives_up_after_max_retries():
    bot = FakeBot(fail_times=BroadcastService.MAX_RETRIES + 1)
    service = BroadcastService(bot)  # type: ignore[arg-type]

    with patch("app.services.broadcast.asyncio.sleep", no_sleep):
        ok = await service._send_single_message(user_id=42, message=FakeTextMessage())  # type: ignore[arg-type]

    assert ok is False
    assert bot.sent == []


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
