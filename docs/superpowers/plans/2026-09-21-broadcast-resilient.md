# Устойчивая рассылка — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рассылка на 150 000 пользователей без бана Telegram, в фоне, с остановкой из админки и возобновлением после рестарта бота.

**Architecture:** `BroadcastService` переписывается по образцу `LivenessService` (`app/services/liveness.py`): синглтон с фоновой задачей, последовательная отправка с ровным темпом `BROADCAST_RATE_LIMIT_RPS`, получатели курсором по `users.id` пачками, каждые 50 отправок курсор и счётчики пишутся в новую таблицу `broadcasts`. Контент — JSON исходного сообщения админа, отправка через `Message.send_copy()` с подменой текста на `html_text` (чтобы `CustomEmojiMiddleware` превратил эмодзи в иконки). При старте бота незавершённая рассылка (`status=running`) продолжается с курсора.

**Tech Stack:** Python 3.11, aiogram 3.31, SQLAlchemy async + asyncpg, pytest (харнес `tests/harness.py`, `FakeDb` в `tests/conftest.py`), `just check` (ruff + pytest + secrets scan).

**Спека:** `docs/superpowers/specs/2026-09-21-broadcast-resilient-design.md` — источник истины при расхождениях.

---

## Правила для всех задач

- Ветка `feat/broadcast-resilient` уже создана — работать в ней. Не переходить на `main`.
- **Не читать** `.env`, `.env.*`, `logs/`, `.deploy/` (запрещено в `.claude/settings.json`). `.env.example` — только дописывать через `printf >>`, не читать.
- Язык: комментарии, докстринги и тексты для пользователя — по-русски; идентификаторы — по-английски.
- Эмодзи в UI-текстах — только из `SUPPORTED_EMOJI` (`app/ui/icons.py`). Все эмодзи в этом плане (`📤 ✅ ❌ 🚫 👥 📈 ⏱ ⏹ 🔄 ⬅️ ⚠️`) там есть; новых не добавлять. Инвентарный тест `tests/test_icons.py` это проверяет.
- После каждой задачи: `just check` зелёный, затем commit. Команда тестов: `.venv/bin/python -m pytest <путь> -v`.
- `app.services.broadcast` **не экспортировать как экземпляр из `app/services/__init__.py`** — иначе атрибут `app.services.broadcast` станет экземпляром и сломает `patch("app.services.broadcast.asyncio.sleep")` в существующих тестах (с `liveness` так уже случилось, см. `importlib` в `tests/test_liveness.py`). Импортировать синглтон так: `from app.services.broadcast import broadcast`.
- Старые методы `send_broadcast` / `_send_single_message` / `_send_once` живут до задачи 5, чтобы старый хендлер и его тесты оставались зелёными между задачами.

## Файлы

| Файл | Задача | Что |
|---|---|---|
| `app/database/models.py` | 1 | модель `Broadcast`, `BROADCAST_FINAL_STATUSES` |
| `app/database/migrations/versions/20260921_000001_add_broadcasts.py` | 1 | таблица `broadcasts` |
| `app/database/database.py` | 1 | 6 методов `db` |
| `tests/conftest.py` | 1 | `FakeDb`: рассылки, `get_alive_user_ids` |
| `app/config.py` | 2 | `broadcast_rate_limit_rps` |
| `app/services/broadcast.py` | 2, 3, 4, 5 | новый сервис (по частям), удаление старого кода в 5 |
| `tests/test_broadcast.py` | 2–6 | тесты сервиса и хендлеров |
| `app/services/liveness.py` | 4 | отказ при идущей рассылке |
| `app/keyboards/admin.py` | 5 | `broadcast_running()`, `broadcast_done()` |
| `app/handlers/admin/admin.py` | 5 | JSON в state, фон, колбэки, строка в `/admin` |
| `tests/harness.py` | 5 | `data_of()` |
| `tests/test_bot_blocked.py` | 5 | удалить 2 теста старого API |
| `app/main.py` | 6 | `configure`, `resume_pending`, `stop_for_shutdown` |
| `AGENTS.md`, `README.md`, `.env.example` | 7 | документация |

---

### Task 1: Таблица `broadcasts`, методы `db`, `FakeDb`

**Files:**
- Modify: `app/database/models.py` (после `LivenessCheck`, конец файла)
- Create: `app/database/migrations/versions/20260921_000001_add_broadcasts.py`
- Modify: `app/database/database.py` (импорт моделей строка 14; новые методы перед `get_migration_history`, строка ~307)
- Modify: `tests/conftest.py` (`FakeDb.__init__`, новые методы, список в фикстуре `fake_db`)
- Test: `tests/test_broadcast.py` (новый блок в конце файла)

- [ ] **Step 1: Тест `FakeDb` — курсор живых и жизненный цикл строки**

Добавить в конец `tests/test_broadcast.py`:

```python
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
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -k fake_db -v`
Expected: 2 FAILED — `AttributeError: 'FakeDb' object has no attribute 'get_alive_user_ids'` / `create_broadcast`.

- [ ] **Step 3: Модель `Broadcast`**

В `app/database/models.py` добавить в конец файла:

```python


BROADCAST_FINAL_STATUSES = ("done", "stopped", "failed")


class Broadcast(Base):
    """Рассылка: контент, курсор по users.id и счётчики — чтобы продолжить после рестарта бота"""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # running — идёт (или прервана рестартом и ждёт возобновления); done / stopped / failed — финальные
    status: Mapped[str] = mapped_column(String(20), default="running", server_default="running", nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Message.model_dump_json() исходного сообщения админа: отправляется через send_copy без Telegram
    content: Mapped[str] = mapped_column(Text, nullable=False)
    button_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    button_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # Курсор: последний обработанный users.id; возобновление идёт с него
    last_user_id: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    blocked: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Broadcast(id={self.id}, status={self.status}, sent={self.sent}/{self.total})>"
```

- [ ] **Step 4: Миграция**

Создать `app/database/migrations/versions/20260921_000001_add_broadcasts.py`:

```python
"""
Таблица рассылок: контент, курсор и счётчики для возобновления после рестарта
"""
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database.migrations.base import Migration


class AddBroadcastsMigration(Migration):
    """Добавляет таблицу broadcasts"""

    def get_version(self) -> str:
        return "20260921_000001"

    def get_description(self) -> str:
        return "Add broadcasts table"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'broadcasts'
            );
        """))
        return not result.scalar()

    async def upgrade(self, connection: AsyncConnection) -> None:
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id SERIAL PRIMARY KEY,
                status VARCHAR(20) NOT NULL DEFAULT 'running',
                created_by BIGINT NOT NULL,
                content TEXT NOT NULL,
                button_text VARCHAR(255),
                button_url VARCHAR(2048),
                total INTEGER NOT NULL DEFAULT 0,
                last_user_id BIGINT NOT NULL DEFAULT 0,
                sent INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                blocked INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMP WITH TIME ZONE
            );
        """))
        logger.info("✅ Added broadcasts table")

    async def downgrade(self, connection: AsyncConnection) -> None:
        await connection.execute(text("DROP TABLE IF EXISTS broadcasts;"))
        logger.info("✅ Removed broadcasts table")
```

- [ ] **Step 5: Методы `db`**

В `app/database/database.py` заменить строку импорта моделей:

```python
from .models import BROADCAST_FINAL_STATUSES, Base, BotStats, Broadcast, LivenessCheck, MigrationHistory, User
```

И вставить перед `async def get_migration_history`:

```python
    # ==================== Рассылки (BroadcastService) ====================

    async def get_alive_user_ids(self, after_id: int, limit: int) -> List[int]:
        """Очередная пачка id живых получателей рассылки (курсор по id)"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(User.id)
                .where(*self._alive_clause(), User.id > after_id)
                .order_by(User.id)
                .limit(limit)
            )
            return result.scalars().all()

    async def create_broadcast(
        self, *, created_by: int, content: str, button_text: Optional[str], button_url: Optional[str], total: int
    ) -> int:
        """Создать запись рассылки со статусом running, вернуть её id"""
        async with self.session_maker() as session:
            row = Broadcast(
                created_by=created_by, content=content, button_text=button_text, button_url=button_url, total=total
            )
            session.add(row)
            await session.commit()
            return row.id

    async def get_broadcast(self, broadcast_id: int) -> Optional[Broadcast]:
        async with self.session_maker() as session:
            return await session.get(Broadcast, broadcast_id)

    async def get_running_broadcast(self) -> Optional[Broadcast]:
        """Незавершённая рассылка — кандидат на возобновление после рестарта (инвариант: не больше одной)"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(Broadcast).where(Broadcast.status == "running").order_by(Broadcast.id.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    async def get_last_broadcast(self) -> Optional[Broadcast]:
        """Последняя рассылка (любой статус) — для панели /admin"""
        async with self.session_maker() as session:
            result = await session.execute(select(Broadcast).order_by(Broadcast.id.desc()).limit(1))
            return result.scalar_one_or_none()

    async def update_broadcast(
        self, broadcast_id: int, *, last_user_id: int, sent: int, failed: int, blocked: int,
        status: Optional[str] = None,
    ) -> None:
        """Чекпоинт: курсор и счётчики; финальный статус проставляет finished_at"""
        values = dict(last_user_id=last_user_id, sent=sent, failed=failed, blocked=blocked)
        if status is not None:
            values["status"] = status
            if status in BROADCAST_FINAL_STATUSES:
                values["finished_at"] = datetime.now(UTC)
        async with self.session_maker() as session:
            await session.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(**values))
            await session.commit()

```

- [ ] **Step 6: `FakeDb`**

В `tests/conftest.py`:

Импорт моделей (строка 25):
```python
from app.database.models import BROADCAST_FINAL_STATUSES, BotStats, Broadcast, LivenessCheck, User  # noqa: E402
```

В `FakeDb.__init__` после `self.liveness_checks`:
```python
        self.broadcasts: Dict[int, Broadcast] = {}
```

После метода `get_last_completed_liveness_check` добавить:

```python
    # --- рассылки (BroadcastService) ---

    async def get_alive_user_ids(self, after_id: int, limit: int) -> List[int]:
        ids = sorted(u.id for u in self.users.values() if u.is_active and not u.bot_blocked and u.id > after_id)
        return ids[:limit]

    async def create_broadcast(self, *, created_by, content, button_text, button_url, total) -> int:
        row = Broadcast(id=len(self.broadcasts) + 1, status="running", created_by=created_by, content=content,
                        button_text=button_text, button_url=button_url, total=total, last_user_id=0,
                        sent=0, failed=0, blocked=0, created_at=datetime.now(UTC), finished_at=None)
        self.broadcasts[row.id] = row
        return row.id

    async def get_broadcast(self, broadcast_id: int) -> Optional[Broadcast]:
        return self.broadcasts.get(broadcast_id)

    async def get_running_broadcast(self) -> Optional[Broadcast]:
        running = [b for b in self.broadcasts.values() if b.status == "running"]
        return max(running, key=lambda b: b.id) if running else None

    async def get_last_broadcast(self) -> Optional[Broadcast]:
        return max(self.broadcasts.values(), key=lambda b: b.id) if self.broadcasts else None

    async def update_broadcast(self, broadcast_id: int, *, last_user_id, sent, failed, blocked, status=None) -> None:
        self.calls.append(("update_broadcast", {"id": broadcast_id, "last_user_id": last_user_id, "sent": sent,
                                                "failed": failed, "blocked": blocked, "status": status}))
        row = self.broadcasts[broadcast_id]
        row.last_user_id, row.sent, row.failed, row.blocked = last_user_id, sent, failed, blocked
        if status is not None:
            row.status = status
            if status in BROADCAST_FINAL_STATUSES:
                row.finished_at = datetime.now(UTC)
```

В фикстуре `fake_db` дополнить кортеж имён:
```python
                 "create_liveness_check", "update_liveness_check", "get_last_completed_liveness_check",
                 "get_alive_user_ids", "create_broadcast", "get_broadcast", "get_running_broadcast",
                 "get_last_broadcast", "update_broadcast"):
```

- [ ] **Step 7: Тесты проходят**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -k fake_db -v`
Expected: 2 passed.

- [ ] **Step 8: `just check` и commit**

Run: `just check` — Expected: ruff `All checks passed!`, все тесты passed, `✅ Секретов в коде не найдено`.

```bash
git add app/database/models.py app/database/migrations/versions/20260921_000001_add_broadcasts.py app/database/database.py tests/conftest.py tests/test_broadcast.py
git commit -m "feat(broadcast): таблица broadcasts, курсор живых получателей, FakeDb"
```

---

### Task 2: Настройка темпа, `build_send_method` и `_send` (одна отправка с вердиктом)

**Files:**
- Modify: `app/config.py` (после `liveness_rate_limit_rps`, строка ~64)
- Modify: `app/services/broadcast.py` (новые импорты, константы, `BroadcastProgress`, `build_send_method`; в `BroadcastService` — `__init__`, `configure`, `_send`, `_mark_blocked`; старые методы остаются)
- Test: `tests/test_broadcast.py`

Контекст: сейчас `BroadcastService.__init__(self, bot)` и старая логика в `send_broadcast/_send_single_message/_send_once`. Их не трогать — удалим в задаче 5.

- [ ] **Step 1: Тестовая обвязка и тесты `build_send_method` / `_send`**

В начале `tests/test_broadcast.py` заменить импорты на:

```python
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
from app.services.broadcast import MAX_RETRIES, BroadcastService, ProgressReporter, build_send_method

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


async def no_sleep(_seconds: float) -> None:
    pass
```

(Старые `FakeProgressMessage` и тесты `ProgressReporter` остаются как есть, но **старое определение `no_sleep` после `FakeProgressMessage` удалить** — остаётся только новое в шапке, иначе ruff F811. Старый `class FakeBot` с `send_message`, `FakeTextMessage` и оба теста `test_send_single_message_*` — **удалить** сейчас; их заменяют тесты ниже. Тесты `confirm_broadcast` внизу файла пока не трогать.)

После блока тестов `ProgressReporter` добавить:

```python
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
    assert list(service._error_kinds) == ["BadRequest:Telegram server says - Bad Request: wron"]
```

- [ ] **Step 2: Тесты падают**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -v`
Expected: ImportError `cannot import name 'MAX_RETRIES' from 'app.services.broadcast'`.

- [ ] **Step 3: Настройка `BROADCAST_RATE_LIMIT_RPS`**

В `app/config.py` после строки `liveness_rate_limit_rps` добавить:

```python
    # Рассылка (app/services/broadcast.py): сообщений в секунду. Telegram допускает ~30/с суммарно,
    # оставляем запас на обычные ответы бота. 150 000 получателей при 20/с ≈ 2 ч
    broadcast_rate_limit_rps: int = Field(20, alias="BROADCAST_RATE_LIMIT_RPS")
```

- [ ] **Step 4: Реализация — импорты, константы, `BroadcastProgress`, `build_send_method`, `_send`**

В `app/services/broadcast.py` заменить докстринг модуля и импорты (строки 1–12) на:

```python
"""
Рассылка: фоновая задача с ровным темпом, курсором по users.id и возобновлением после рестарта.

Telegram допускает ~30 сообщений/с суммарно по всем чатам. Отправляем последовательно, темп задаём
до запроса (BROADCAST_RATE_LIMIT_RPS); на 429 ждём весь retry_after — поток один, поэтому пауза
глобальная. Получатели читаются курсором пачками (память постоянная); каждые CHECKPOINT_EVERY
отправок курсор и счётчики пишутся в строку broadcasts. При старте бота незавершённая рассылка
(status=running) продолжается с курсора (resume_pending); при kill -9 до CHECKPOINT_EVERY
получателей могут получить сообщение дважды — при штатном SIGTERM курсор точный.

Контент — JSON исходного сообщения админа (Message.model_dump_json), отправка через send_copy.
Текст/подпись подменяются на html_text без entities: CustomEmojiMiddleware не трогает текст
с явными entities, а так эмодзи становятся иконками и форматирование сохраняется.

ProgressReporter — общий для долгих операций (рассылка, проверка живых) троттлинг правок прогресса.
"""
import asyncio
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, Literal, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import InlineKeyboardMarkup, Message
from loguru import logger

from app.database import db

# Импорты settings, AdminKeyboards (задача 3), notify_admins, liveness (задача 4) добавляются там,
# где появляется использующий их код — иначе ruff F401 и красный just check на промежуточных коммитах

BATCH_SIZE = 500            # id получателей на один запрос к БД
CHECKPOINT_EVERY = 50       # отправок между записями курсора в БД
PROGRESS_EVERY_SECONDS = 5  # не чаще — колбэк прогресса (он редактирует сообщение админа)
MAX_RETRIES = 3             # попыток отправки одному получателю всего (как в liveness), не повторов

Verdict = Literal["sent", "blocked", "failed"]
```

`ProgressReporter` оставить без изменений. Между `ProgressReporter` и `class BroadcastService` вставить:

```python
@dataclass
class BroadcastProgress:
    broadcast_id: int
    total: int
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    status: str = "running"  # после завершения: done / stopped / failed; running — прервана рестартом
    started_at: float = field(default_factory=time.monotonic)
    finished_at: Optional[float] = None

    @property
    def processed(self) -> int:
        return self.sent + self.failed + self.blocked

    @property
    def percent(self) -> int:
        return min(100, self.processed * 100 // self.total) if self.total else 100

    @property
    def elapsed(self) -> timedelta:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return timedelta(seconds=int(end - self.started_at))


ProgressCallback = Callable[[BroadcastProgress], Awaitable[None]]


def build_send_method(message: Message, chat_id: int, keyboard: Optional[InlineKeyboardMarkup]) -> TelegramMethod:
    """Send* по типу сообщения. Текст/подпись — как HTML без entities, чтобы сработали иконки.

    TypeError от send_copy (тип не поддерживается) не ловим: он одинаков для всех получателей
    и должен уронить рассылку целиком, а не дать 150 000 «failed».
    """
    method = message.send_copy(chat_id=chat_id, reply_markup=keyboard)
    if isinstance(method, SendMessage):
        return method.model_copy(update={"text": message.html_text, "entities": None, "parse_mode": "HTML"})
    if getattr(method, "caption", None) is not None:
        return method.model_copy(update={"caption": message.html_text, "caption_entities": None, "parse_mode": "HTML"})
    return method
```

В `class BroadcastService` заменить докстринг, `MAX_RETRIES` класса и `__init__` (строки `"""Сервис для рассылки сообщений"""` … `self.bot = bot`) на:

```python
class BroadcastService:
    """Одна рассылка за раз (в рамках процесса); синглтон `broadcast`, configure(bot) в main.py"""

    def __init__(self, bot: Optional[Bot] = None):
        self.bot = bot
        self._task: Optional[asyncio.Task] = None
        self.progress: Optional[BroadcastProgress] = None   # текущая рассылка
        self.last_result: Optional[BroadcastProgress] = None
        self._stop_requested = False   # stop() из админки → stopped; отмена без него (shutdown) → running
        self._error_kinds: Counter = Counter()  # что именно ломалось в текущей рассылке

    def configure(self, bot: Bot) -> None:
        self.bot = bot

    async def _send(self, user_id: int, message: Message, keyboard: Optional[InlineKeyboardMarkup]) -> Verdict:
        """Одному получателю: 'sent' | 'blocked' | 'failed'. На 429 ждём весь retry_after."""
        method = build_send_method(message, user_id, keyboard)
        for _ in range(MAX_RETRIES):
            try:
                await self.bot(method)
                return "sent"
            except TelegramRetryAfter as e:
                logger.warning(f"📤 broadcast: флуд-лимит Telegram, ждём {e.retry_after} с")
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                await self._mark_blocked(user_id)
                return "blocked"
            except TelegramBadRequest as e:
                text = str(e).lower()
                if "chat not found" in text or "user is deactivated" in text:
                    await self._mark_blocked(user_id)
                    return "blocked"
                self._error_kinds[f"BadRequest:{str(e)[:40]}"] += 1
                logger.debug(f"📤 broadcast: ошибка отправки {user_id}: {e}")
                return "failed"
            except Exception as e:
                self._error_kinds[type(e).__name__] += 1
                logger.debug(f"📤 broadcast: ошибка отправки {user_id}: {e}")
                return "failed"
        self._error_kinds["RetryAfter:exhausted"] += 1
        logger.debug(f"📤 broadcast: {user_id} пропущен — {MAX_RETRIES} флуд-лимита подряд")
        return "failed"

    async def _mark_blocked(self, user_id: int) -> None:
        """Заблокировал бота или удалил аккаунт — больше не слать"""
        try:
            await db.set_bot_blocked(user_id, True)
        except Exception as e:
            logger.warning(f"Не удалось пометить {user_id} как заблокировавшего бота: {e}")
```

Старые `MAX_RETRIES = 3` внутри класса удалить (теперь модульная константа); в `_send_single_message` заменить `self.MAX_RETRIES` на `MAX_RETRIES`. Старые методы `send_broadcast`, `_send_single_message`, `_send_once` оставить.

`settings`, `AdminKeyboards`, `notify_admins`, `liveness` в этой задаче **не импортировать** — они ещё не используются (ruff F401).

- [ ] **Step 5: Тесты проходят**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py tests/test_bot_blocked.py -v`
Expected: все passed (в `test_bot_blocked.py` два старых теста ещё используют `BroadcastService(bot)` — конструктор совместим).

Ключ в `test_send_counts_other_bad_request_as_failed` — первые 40 символов `str(TelegramBadRequest)` (`"Telegram server says - Bad Request: wron"`, проверено на aiogram 3.31).

- [ ] **Step 6: `just check` и commit**

```bash
git add app/config.py app/services/broadcast.py tests/test_broadcast.py
git commit -m "feat(broadcast): build_send_method (send_copy + html_text), _send с вердиктом, BROADCAST_RATE_LIMIT_RPS"
```

---

### Task 3: Цикл `run`: ровный темп, курсор, чекпоинты, статусы

**Files:**
- Modify: `app/services/broadcast.py` (`BroadcastService.run`, `_checkpoint`, `_errors_summary`)
- Test: `tests/test_broadcast.py`

- [ ] **Step 1: Тесты цикла**

Добавить в `tests/test_broadcast.py` (после тестов `_send`):

```python
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
```

- [ ] **Step 2: Тесты падают**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -k "test_run" -v`
Expected: FAILED — `AttributeError: 'BroadcastService' object has no attribute 'run'` (и `is_running`).

- [ ] **Step 3: Реализация `run`**

Добавить импорты в `app/services/broadcast.py` (после `from app.database import db`):

```python
from app.keyboards import AdminKeyboards
```

и перед ним `from app.config import settings` (по алфавиту: `app.config`, `app.database`, `app.keyboards`). Служебный комментарий про отложенные импорты из задачи 2 можно удалить.

В `BroadcastService` после `configure` добавить:

```python
    def _task_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def is_running(self) -> bool:
        """Идёт ли рассылка — включая вызов run() напрямую, без start()"""
        return self._task_running() or self.progress is not None

    async def run(self, broadcast_id: int, progress_callback: Optional[ProgressCallback] = None) -> BroadcastProgress:
        """Одна рассылка от курсора до конца. При отмене дописывает курсор; статус — см. except."""
        if self.bot is None:
            raise RuntimeError("BroadcastService не сконфигурирован (bot=None)")
        row = await db.get_broadcast(broadcast_id)
        if row is None or row.status != "running":
            raise RuntimeError(f"Рассылка #{broadcast_id} не найдена или уже завершена")
        progress = BroadcastProgress(broadcast_id, total=row.total, sent=row.sent, failed=row.failed, blocked=row.blocked)
        self.progress = progress
        self.last_result = None  # чтобы наблюдатель не показал итог прошлой рассылки
        self._stop_requested = False
        self._error_kinds = Counter()
        delay = 1 / max(settings.broadcast_rate_limit_rps, 1)
        next_at = time.monotonic()
        after_id = row.last_user_id
        last_report = 0.0  # первый прогресс-колбэк — сразу
        since_checkpoint = 0
        logger.info(f"📤 Broadcast #{broadcast_id} started at {progress.processed}/{progress.total}")

        try:
            # Восстановление контента внутри try: невалидный JSON должен закончиться status=failed,
            # иначе строка останется running и resume_pending() будет поднимать её на каждом рестарте
            message = Message.model_validate_json(row.content)
            keyboard = None
            if row.button_text and row.button_url:
                keyboard = AdminKeyboards.create_custom_button(row.button_text, row.button_url)
            while True:
                ids = await db.get_alive_user_ids(after_id, BATCH_SIZE)
                if not ids:
                    break
                for uid in ids:
                    # Темп задаём до запроса: сеть может отвечать сколь угодно долго,
                    # но частота запросов остаётся ≈ broadcast_rate_limit_rps
                    await asyncio.sleep(max(0.0, next_at - time.monotonic()))
                    next_at = max(next_at, time.monotonic()) + delay

                    verdict = await self._send(uid, message, keyboard)
                    setattr(progress, verdict, getattr(progress, verdict) + 1)
                    after_id = uid
                    since_checkpoint += 1

                    if since_checkpoint >= CHECKPOINT_EVERY:
                        await self._checkpoint(progress, after_id)
                        since_checkpoint = 0
                    if progress_callback and time.monotonic() - last_report >= PROGRESS_EVERY_SECONDS:
                        last_report = time.monotonic()
                        try:
                            await progress_callback(progress)
                        except Exception as e:
                            logger.debug(f"broadcast progress callback failed: {e}")
            progress.status = "done"
        except asyncio.CancelledError:
            # stop() из админки → stopped (финал); отмена на shutdown → running, чтобы возобновиться после рестарта
            progress.status = "stopped" if self._stop_requested else "running"
            logger.info(f"📤 Broadcast #{broadcast_id} cancelled at {progress.processed}/{progress.total} → {progress.status}")
            raise
        except Exception as e:
            progress.status = "failed"
            logger.exception(f"❌ Broadcast #{broadcast_id} failed at {progress.processed}/{progress.total}: {e}")
            raise
        finally:
            progress.finished_at = time.monotonic()
            try:
                await self._checkpoint(progress, after_id, status=progress.status)
            except Exception as e:
                logger.exception(f"❌ Не удалось записать итог рассылки #{broadcast_id}: {e}")
            self.last_result = progress
            self.progress = None
            logger.info(
                f"📤 Broadcast #{broadcast_id} {progress.status}: sent={progress.sent} failed={progress.failed} "
                f"blocked={progress.blocked} of {progress.total}{self._errors_summary()}"
            )
        return progress

    async def _checkpoint(self, progress: BroadcastProgress, after_id: int, status: Optional[str] = None) -> None:
        """Курсор и счётчики в БД; status='running' на shutdown не проставляет finished_at"""
        await db.update_broadcast(
            progress.broadcast_id, last_user_id=after_id, sent=progress.sent, failed=progress.failed,
            blocked=progress.blocked, status=status,
        )

    def _errors_summary(self) -> str:
        """Топ-5 видов ошибок — чтобы не разбирать логи по одному получателю"""
        if not self._error_kinds:
            return ""
        return f" kinds={dict(self._error_kinds.most_common(5))}"
```

- [ ] **Step 4: Тесты проходят**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -v`
Expected: все passed.

- [ ] **Step 5: `just check` и commit**

```bash
git add app/services/broadcast.py tests/test_broadcast.py
git commit -m "feat(broadcast): цикл run — ровный темп, курсор по id, чекпоинты, статусы done/stopped/failed"
```

---

### Task 4: Фоновая задача: `start/stop/stop_for_shutdown/wait`, `resume_pending`, тексты, взаимоисключение с liveness

**Files:**
- Modify: `app/services/broadcast.py` (методы жизненного цикла, `_watchers`, `format_broadcast_progress`, `format_broadcast_result`, синглтон `broadcast`)
- Modify: `app/services/liveness.py` (`start()`: ленивый импорт и проверка)
- Test: `tests/test_broadcast.py`

- [ ] **Step 1: Тесты**

Дополнить импорты в `tests/test_broadcast.py`:

```python
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
```

Добавить фикстуру после `sleeps`:

```python
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
```

Тесты (после блока `run`):

```python
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
```

- [ ] **Step 2: Тесты падают**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -v`
Expected: ImportError `cannot import name 'BroadcastProgress'`… (нет `broadcast`, `format_broadcast_result`).

- [ ] **Step 3: Реализация жизненного цикла и текстов**

Добавить импорты в `app/services/broadcast.py` (после `from app.keyboards import AdminKeyboards`):

```python
from app.services.admins import notify_admins
from app.services.liveness import liveness
```

`notify_admins` вызывать как имя модуля (`await notify_admins(...)`), не переимпортировать внутри функций — тесты подменяют его через `monkeypatch.setattr(broadcast_module, "notify_admins", …)`.

Циклического импорта нет: `liveness.py` не импортирует `broadcast` на уровне модуля (Step 4 добавит ленивый импорт внутри `start()`).

В `BroadcastService` после `is_running` добавить:

```python
    def start(self, broadcast_id: int, progress_callback: Optional[ProgressCallback] = None) -> Optional[asyncio.Task]:
        """Запустить рассылку в фоне. None — если идёт рассылка или проверка живых (общий лимит Telegram)."""
        if self.is_running() or liveness.is_running():
            return None
        self._task = asyncio.create_task(self.run(broadcast_id, progress_callback), name=f"broadcast-{broadcast_id}")
        return self._task

    def stop(self) -> bool:
        """Остановить из админки: статус stopped (финальный). True — если было что останавливать."""
        if not self._task_running():
            return False
        self._stop_requested = True
        self._task.cancel()
        return True

    def stop_for_shutdown(self) -> bool:
        """Прервать на выключении бота: статус остаётся running, рассылка возобновится после рестарта."""
        if not self._task_running():
            return False
        self._task.cancel()
        return True

    async def wait(self, timeout: Optional[float] = None) -> None:
        """Дождаться завершения (в т.ч. после stop()). asyncio.wait — не глушит CancelledError вызывающего."""
        if self._task is None:
            return
        await asyncio.wait({self._task}, timeout=timeout)
        self._log_outcome(self._task)

    @staticmethod
    def _log_outcome(task: asyncio.Task) -> None:
        """Забрать исключение задачи, чтобы оно не потерялось и не всплыло в GC"""
        if not task.done():
            logger.warning("📤 Broadcast: рассылка не завершилась за отведённое время")
            return
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.opt(exception=exc).error("❌ Broadcast crashed")

    async def resume_pending(self) -> None:
        """При старте бота: продолжить рассылку, прерванную рестартом. Итог — всем админам."""
        row = await db.get_running_broadcast()
        if row is None:
            return
        task = self.start(row.id)
        if task is None:
            logger.warning(f"📤 Broadcast #{row.id} не возобновлена: занято — останется running до следующего рестарта")
            return
        logger.info(f"📤 Broadcast #{row.id} resumed at {row.sent + row.failed + row.blocked}/{row.total}")

        async def watch() -> None:
            await asyncio.wait({task})
            self._log_outcome(task)
            result = self.last_result
            if result is None or result.status == "running":
                return  # снова прервана рестартом — итог придёт после следующего
            await notify_admins(self.bot, format_broadcast_result(result))

        watcher = asyncio.create_task(watch(), name=f"broadcast-{row.id}-watch")
        _watchers.add(watcher)
        watcher.add_done_callback(_watchers.discard)
```

Перед `class BroadcastService` (после `build_send_method`) добавить:

```python
# Ссылки на наблюдателей возобновлённых рассылок, чтобы задачи не собрал GC
_watchers: set[asyncio.Task] = set()
```

В конец файла добавить:

```python
STATUS_TITLES = {
    "done": "✅ <b>Рассылка завершена</b>",
    "stopped": "⏹ <b>Рассылка остановлена</b>",
    "failed": "❌ <b>Рассылка упала</b>",
}
STATUS_LABELS = {"running": "идёт", "done": "завершена", "stopped": "остановлена", "failed": "упала"}


def format_broadcast_progress(progress: BroadcastProgress) -> str:
    return (
        "📤 <b>Рассылка…</b>\n\n"
        f"Отправлено: <b>{progress.processed}</b> из {progress.total} ({progress.percent}%)\n"
        f"✅ доставлено: {progress.sent} · ❌ ошибок: {progress.failed} · 🚫 заблокировали: {progress.blocked}\n"
        f"⏱ {progress.elapsed}"
    )


def format_broadcast_result(result: BroadcastProgress) -> str:
    """Итог рассылки для админа (сообщение прогресса или уведомление после возобновления)"""
    success = int(result.sent * 100 / result.total) if result.total else 0
    lines = [STATUS_TITLES.get(result.status, STATUS_TITLES["failed"]), ""]
    if result.status == "stopped":
        lines.append(f"Остановлена на <b>{result.processed}</b> из {result.total}")
    lines += [
        f"👥 Получателей: <b>{result.total}</b>",
        f"✅ Доставлено: <b>{result.sent}</b>",
        f"❌ Ошибок: <b>{result.failed}</b>",
        f"🚫 Заблокировали бота: <b>{result.blocked}</b>",
        f"📈 Успешность: <b>{success}%</b>",
        f"⏱ Длительность: {result.elapsed}",
    ]
    return "\n".join(lines)


# Глобальный экземпляр: configure(bot) в main.py и в хендлере подтверждения.
# Не экспортировать из app/services/__init__.py — атрибут app.services.broadcast должен остаться модулем
broadcast = BroadcastService()
```

- [ ] **Step 4: Liveness отказывает при идущей рассылке**

В `app/services/liveness.py` метод `start` заменить на:

```python
    def start(self, trigger: str, progress_callback: Optional[ProgressCallback] = None) -> Optional[asyncio.Task]:
        """Запустить прогон в фоне. None — если прогон или рассылка уже идут (общий лимит Telegram)."""
        from app.services.broadcast import broadcast  # ленивый импорт: broadcast.py импортирует liveness

        if self.is_running() or broadcast.is_running():
            return None
        self._task = asyncio.create_task(self.run_check(trigger, progress_callback), name=f"liveness-{trigger}")
        return self._task
```

(`_maybe_run_scheduled` зовёт `self.start()` — отдельной проверки не нужно.)

- [ ] **Step 5: Тесты проходят**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py tests/test_liveness.py -v`
Expected: все passed. Если `test_resume_pending_continues_and_notifies_admins` падает на `notified == []` — убедиться, что `notify_admins` в `broadcast.py` берётся из модуля (`notify_admins(...)`, не `from … import` внутри функции), иначе `monkeypatch.setattr(broadcast_module, "notify_admins", …)` не сработает.

- [ ] **Step 6: `just check` и commit**

```bash
git add app/services/broadcast.py app/services/liveness.py tests/test_broadcast.py
git commit -m "feat(broadcast): фоновая задача, stop/stop_for_shutdown, resume_pending, тексты, взаимоисключение с liveness"
```

---

### Task 5: Админка: JSON в state, фоновой запуск, стоп/обновить, строка в `/admin`; удаление старого кода

**Files:**
- Modify: `app/keyboards/admin.py` (после `broadcast_confirm`)
- Modify: `app/handlers/admin/admin.py`
- Modify: `tests/harness.py` (`data_of`)
- Modify: `app/services/broadcast.py` (удалить `send_broadcast`, `_send_single_message`, `_send_once`)
- Modify: `app/services/__init__.py` (убрать `BroadcastService` из экспорта — не нужен)
- Modify: `tests/test_bot_blocked.py` (удалить `ForbiddenBot`, `FakeTextMessage`, `test_broadcast_marks_user_blocked_on_forbidden`, `test_broadcast_skips_users_who_blocked_bot`, импорты `TelegramForbiddenError`, `SendMessage`, `BroadcastService`)
- Test: `tests/test_broadcast.py` (блок хендлеров переписать)

- [ ] **Step 1: Тесты хендлеров**

В `tests/harness.py` после `state_of` добавить:

```python
    async def data_of(self, user: Optional[User] = None) -> dict:
        """Данные FSM пользователя."""
        user = user or make_user()
        ctx = self.dp.fsm.get_context(self.bot, chat_id=user.id, user_id=user.id)
        return await ctx.get_data()
```

В `tests/test_broadcast.py` **заменить** весь блок `# --- confirm_broadcast: FSM очищается при любом исходе` (три старых теста и `_arm_confirm_state`) на:

```python
# --- админка: мастер, подтверждение, стоп, панель ----------------------------

from aiogram.methods import AnswerCallbackQuery  # noqa: E402

from app.handlers.admin import admin as admin_handlers  # noqa: E402
from tests.harness import callbacks_of  # noqa: E402


async def _arm_confirm_state(harness, admin, text: str = "Текст рассылки"):
    """Админ уже отправил контент рассылки и видит кнопку подтверждения."""
    await harness.send_message("/start", admin)
    await harness.send_callback("admin_broadcast", admin)
    await harness.send_message(text, admin)
    harness.clear()


async def _drain_handler_watchers() -> None:
    for watcher in list(admin_handlers._watchers):
        await watcher


async def test_receive_broadcast_message_stores_json_string(harness, admin):
    """RedisStorage делает json.dumps — объект Message туда не помещается, только строка."""
    await harness.send_message("/start", admin)
    await harness.send_callback("admin_broadcast", admin)

    await harness.send_message("Текст <рассылки>", admin)

    content = (await harness.data_of(admin))["broadcast_message"]
    assert isinstance(content, str)
    assert Message.model_validate_json(content).text == "Текст <рассылки>"


async def test_confirm_broadcast_starts_background_and_clears_state(harness, admin, fake_db, fresh_broadcast, monkeypatch):
    await fake_db.add_user(1)
    await fake_db.add_user(2)
    await _arm_confirm_state(harness, admin)
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 1000)

    replies = await harness.send_callback("broadcast_confirm_yes", admin)

    assert "Запускаю" in replies[-1].text
    assert "broadcast:stop" in callbacks_of(replies[-1])
    assert await harness.state_of(admin) is None  # хендлер не ждёт конца рассылки
    row = fake_db.broadcasts[1]
    assert (row.created_by, row.total, row.status) == (admin.id, len(fake_db.users), "running")
    assert Message.model_validate_json(row.content).text == "Текст рассылки"

    await fresh_broadcast.wait(timeout=1)
    await _drain_handler_watchers()

    assert fake_db.broadcasts[1].status == "done"
    assert "Рассылка завершена" in harness.last_text
    delivered = [c for c in harness.calls if isinstance(c, SendMessage) and c.chat_id in (1, 2)]
    assert [c.text for c in delivered] == ["Текст рассылки", "Текст рассылки"]


async def test_confirm_broadcast_answers_callback_before_starting(harness, admin, fake_db, fresh_broadcast, monkeypatch):
    """Рассылка идёт долго, а callback query протухает — отвечать надо до старта."""
    await _arm_confirm_state(harness, admin)
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 1000)

    await harness.send_callback("broadcast_confirm_yes", admin)
    await fresh_broadcast.wait(timeout=1)
    await _drain_handler_watchers()

    answered_at = next(i for i, c in enumerate(harness.calls) if isinstance(c, AnswerCallbackQuery))
    started_at = next(i for i, c in enumerate(harness.calls) if isinstance(c, EditMessageText) and "Запускаю" in c.text)
    assert answered_at < started_at


async def test_confirm_broadcast_rejects_second_run(harness, admin, fake_db, fresh_broadcast):
    await _arm_confirm_state(harness, admin)
    fresh_broadcast.progress = BroadcastProgress(broadcast_id=1, total=10, sent=4)

    replies = await harness.send_callback("broadcast_confirm_yes", admin)

    assert fake_db.broadcasts == {}
    assert await harness.state_of(admin) is None
    assert "Рассылка…" in replies[-1].text and "<b>4</b> из 10" in replies[-1].text
    alert = next(c for c in harness.calls if isinstance(c, AnswerCallbackQuery) and c.show_alert)
    assert "уже идёт" in alert.text


async def test_confirm_broadcast_rejects_while_liveness_runs(harness, admin, fake_db, fresh_broadcast):
    await _arm_confirm_state(harness, admin)
    liveness.progress = LivenessProgress(total=1)
    try:
        await harness.send_callback("broadcast_confirm_yes", admin)
    finally:
        liveness.progress = None

    assert fake_db.broadcasts == {}
    assert await harness.state_of(admin) is None
    alert = next(c for c in harness.calls if isinstance(c, AnswerCallbackQuery) and c.show_alert)
    assert "проверка живых" in alert.text


async def test_broadcast_stop_button_cancels_and_reports(harness, admin, fake_db, fresh_broadcast, monkeypatch):
    for uid in range(1, 51):
        await fake_db.add_user(uid)
    await _arm_confirm_state(harness, admin)
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 1000)

    await harness.send_callback("broadcast_confirm_yes", admin)
    await _real_sleep(0.01)
    await harness.send_callback("broadcast:stop", admin)
    await fresh_broadcast.wait(timeout=1)
    await _drain_handler_watchers()

    row = fake_db.broadcasts[1]
    assert row.status == "stopped" and 0 < row.last_user_id
    assert "Рассылка остановлена" in harness.last_text
    assert "broadcast:back" in callbacks_of(harness.sent[-1])


async def test_broadcast_refresh_shows_progress(harness, admin, fresh_broadcast):
    await harness.send_message("/start", admin)
    fresh_broadcast.progress = BroadcastProgress(broadcast_id=1, total=10, sent=4)

    replies = await harness.send_callback("broadcast:refresh", admin)

    assert "<b>4</b> из 10 (40%)" in replies[-1].text


async def test_admin_broadcast_button_opens_progress_when_running(harness, admin, fresh_broadcast):
    await harness.send_message("/start", admin)
    fresh_broadcast.progress = BroadcastProgress(broadcast_id=1, total=5)

    replies = await harness.send_callback("admin_broadcast", admin)

    assert "Рассылка…" in replies[-1].text
    assert "broadcast:stop" in callbacks_of(replies[-1])
    assert await harness.state_of(admin) is None  # мастер не открылся


async def test_admin_panel_shows_running_broadcast(harness, admin, fake_db, fresh_broadcast):
    fresh_broadcast.progress = BroadcastProgress(broadcast_id=1, total=150000, sent=12000, failed=300, blocked=40)

    replies = await harness.send_message("/admin", admin)

    assert "📤 Рассылка: идёт <b>12340 / 150000</b> (8%)" in replies[0].text


async def test_admin_panel_shows_last_broadcast(harness, admin, fake_db):
    bid = await fake_db.create_broadcast(created_by=777, content="{}", button_text=None, button_url=None, total=10)
    await fake_db.update_broadcast(bid, last_user_id=10, sent=9, failed=0, blocked=1, status="done")

    replies = await harness.send_message("/admin", admin)

    assert "📤 Последняя рассылка: <b>" in replies[0].text
    assert "</b> — завершена, 9 / 10" in replies[0].text


async def test_admin_panel_without_broadcasts(harness, admin, fake_db):
    replies = await harness.send_message("/admin", admin)

    assert "📤 Рассылок ещё не было" in replies[0].text
```

Оставить в файле только один импорт `callbacks_of` — если он уже есть наверху, второй не добавлять. Импорты `AnswerCallbackQuery`, `admin_handlers` лучше перенести в верхний блок импортов файла (без `noqa`).

- [ ] **Step 2: Тесты падают**

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -k "receive or confirm or stop_button or refresh or admin_" -v`
Expected: FAILED (нет `data_of`, `_watchers` у хендлеров, нет колбэков `broadcast:*`, старый `confirm_broadcast` ждёт `send_broadcast`).

- [ ] **Step 3: Клавиатуры**

В `app/keyboards/admin.py` после `broadcast_confirm` добавить:

```python
    @staticmethod
    def broadcast_running() -> InlineKeyboardMarkup:
        """Во время рассылки"""
        builder = InlineKeyboardBuilder()
        builder.button(text="⏹ Остановить", callback_data="broadcast:stop")
        builder.button(text="🔄 Обновить", callback_data="broadcast:refresh")
        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def broadcast_done() -> InlineKeyboardMarkup:
        """После рассылки"""
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="broadcast:back")
        builder.adjust(1)
        return builder.as_markup()
```

И в `main_admin_menu` кнопку `text="📊 Рассылка"` заменить на `text="📤 Рассылка"` (везде в UI рассылка — 📤). Это ломает четыре существующих теста — поправить их в этом же шаге:

- `tests/test_handlers.py:44` — `"📊 Рассылка"` → `"📤 Рассылка"`;
- `tests/test_custom_emoji.py:67` — `("Рассылка", Icons.STATS)` → `("Рассылка", Icons.UPLOAD)`;
- `tests/test_custom_emoji.py:77` и `:96` — `"📊 Рассылка"` → `"📤 Рассылка"`.

(Номера строк — на момент написания плана; искать по `grep -n "Рассылка" tests/test_handlers.py tests/test_custom_emoji.py`.)

- [ ] **Step 4: Хендлеры**

В `app/handlers/admin/admin.py`:

Импорты — заменить `from app.services import BroadcastService, ProgressReporter` на:

```python
import asyncio

from app.services.broadcast import (
    STATUS_LABELS,
    BroadcastProgress,
    ProgressReporter,
    broadcast,
    format_broadcast_progress,
    format_broadcast_result,
)
from app.services.liveness import liveness
```

(`import asyncio` — в блок стандартной библиотеки, рядом с `import re`.)

После `router = Router()` добавить:

```python
# Ссылки на наблюдателей за рассылкой, чтобы задачи не собрал GC
_watchers: set[asyncio.Task] = set()


async def _show_broadcast_running(callback: CallbackQuery) -> None:
    """Экран текущей рассылки"""
    if broadcast.progress is not None:
        text = format_broadcast_progress(broadcast.progress)
    else:
        text = "📤 <b>Рассылка…</b>\n\nЗапускаю…"
    await ProgressReporter(callback.message, min_interval=0).update(text, AdminKeyboards.broadcast_running())


async def broadcast_status_line() -> str:
    """Строка о рассылке для панели /admin"""
    progress = broadcast.progress
    if progress is not None:
        return f"📤 Рассылка: идёт <b>{progress.processed} / {progress.total}</b> ({progress.percent}%)"
    last = await db.get_last_broadcast()
    if last is None:
        return "📤 Рассылок ещё не было"
    when = (last.finished_at or last.created_at).strftime("%d.%m %H:%M")
    return f"📤 Последняя рассылка: <b>{when}</b> — {STATUS_LABELS.get(last.status, last.status)}, {last.sent} / {last.total}"
```

В `admin_panel_text`: после `icons_label, icons_note = …` добавить `broadcast_line = await broadcast_status_line()`, а в f-строку после строки `⚙️ Иконки: …` добавить строку `{broadcast_line}`.

`start_broadcast` — после проверки `is_admin` добавить:

```python
    if broadcast.is_running():
        await _show_broadcast_running(callback)
        await callback.answer("Рассылка уже идёт")
        return
```

`receive_broadcast_message` — заменить `await state.update_data(broadcast_message=message)` на:

```python
    # Строка JSON, не объект: RedisStorage хранит данные через json.dumps
    await state.update_data(broadcast_message=message.model_dump_json())
```

`confirm_broadcast` — заменить целиком (вместе с `format_broadcast_report`, который удаляется):

```python
@router.callback_query(F.data == "broadcast_confirm_yes")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot, is_admin: bool = False):
    """Подтверждение: запись в БД и запуск рассылки в фоне; прогресс и итог — в этом же сообщении"""
    if not is_admin:
        await callback.answer("❌ У вас нет прав администратора")
        return

    data = await state.get_data()
    content = data.get("broadcast_message")
    if not content:
        await callback.message.edit_text("❌ Ошибка: сообщение для рассылки не найдено")
        await state.clear()
        return

    if broadcast.is_running():
        await state.clear()
        await _show_broadcast_running(callback)
        await callback.answer("Рассылка уже идёт", show_alert=True)
        return
    if liveness.is_running():
        await state.clear()
        await callback.answer("Идёт проверка живых — дождитесь её окончания", show_alert=True)
        return

    broadcast_id = await db.create_broadcast(
        created_by=callback.from_user.id, content=content,
        button_text=data.get("button_text"), button_url=data.get("button_url"),
        total=await db.get_alive_users_count(),
    )

    # Отвечаем на callback сразу: рассылка идёт долго, а callback query протухает через несколько секунд.
    # State чистим сразу же — хендлер больше не ждёт конца рассылки
    await callback.answer()
    await state.clear()

    broadcast.configure(bot)
    reporter = ProgressReporter(callback.message)

    async def on_progress(progress: BroadcastProgress) -> None:
        await reporter.update(format_broadcast_progress(progress), AdminKeyboards.broadcast_running())

    # Сначала экран «Запускаю…», потом старт: иначе первый прогресс-колбэк
    # может обогнать эту правку и «Запускаю…» перезатрёт прогресс
    await reporter.update("📤 <b>Рассылка…</b>\n\nЗапускаю…", AdminKeyboards.broadcast_running())

    task = broadcast.start(broadcast_id, on_progress)
    if task is None:
        # Проиграли гонку другому админу или планировщику liveness между проверкой выше и стартом
        await db.update_broadcast(broadcast_id, last_user_id=0, sent=0, failed=0, blocked=0, status="failed")
        reason = "идёт проверка живых" if liveness.is_running() else "рассылка уже идёт"
        await reporter.finish(f"⚠️ Рассылка не запущена: {reason}", AdminKeyboards.broadcast_done())
        return

    async def watch() -> None:
        await asyncio.wait({task})
        if task.cancelled():
            result = broadcast.last_result  # run() дописывает итог в finally перед raise
            if result is not None and result.status != "running":  # running — бот выключается, итог после рестарта
                await reporter.finish(format_broadcast_result(result), AdminKeyboards.broadcast_done())
        elif (exc := task.exception()) is not None:
            logger.opt(exception=exc).error("❌ Broadcast crashed")
            await reporter.finish("❌ Рассылка упала, подробности в логах", AdminKeyboards.broadcast_done())
        else:
            await reporter.finish(format_broadcast_result(task.result()), AdminKeyboards.broadcast_done())

    watcher = asyncio.create_task(watch())
    _watchers.add(watcher)
    watcher.add_done_callback(_watchers.discard)


@router.callback_query(F.data == "broadcast:stop", IsAdmin())
async def broadcast_stop(callback: CallbackQuery) -> None:
    """Остановить текущую рассылку; итог допишет наблюдатель из confirm_broadcast"""
    if broadcast.stop():
        await callback.answer("Останавливаю…")
    else:
        await callback.answer("Рассылка не идёт")


@router.callback_query(F.data == "broadcast:refresh", IsAdmin())
async def broadcast_refresh(callback: CallbackQuery) -> None:
    """Обновить экран рассылки вручную"""
    if broadcast.is_running():
        await _show_broadcast_running(callback)
        await callback.answer()
        return
    result = broadcast.last_result
    if result is not None and result.status != "running":
        await ProgressReporter(callback.message, min_interval=0).update(
            format_broadcast_result(result), AdminKeyboards.broadcast_done()
        )
    await callback.answer("Рассылка не идёт")


@router.callback_query(F.data == "broadcast:back", IsAdmin())
async def broadcast_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text(await admin_panel_text(), reply_markup=AdminKeyboards.main_admin_menu())
    await callback.answer()
```

Проверить, что `logger` по-прежнему используется (в `watch`) — иначе ruff F401.

- [ ] **Step 5: Удалить старый код сервиса и старые тесты**

В `app/services/broadcast.py` удалить методы `send_broadcast`, `_send_single_message`, `_send_once` целиком и `Dict` из `from typing import …` (больше не используется; `Any`, `Awaitable`, `Callable` нужны `ProgressReporter`). Затем `ruff check app/services/broadcast.py`.

В `app/services/__init__.py`:

```python
from .admins import notify_admins
from .broadcast import ProgressReporter
from .liveness import LivenessService, liveness

__all__ = ["LivenessService", "ProgressReporter", "liveness", "notify_admins"]
```

В `tests/test_bot_blocked.py` удалить `ForbiddenBot`, `FakeTextMessage`, `test_broadcast_marks_user_blocked_on_forbidden`, `test_broadcast_skips_users_who_blocked_bot` и ставшие лишними импорты (`TelegramForbiddenError`, `SendMessage`, `BroadcastService`). Эти сценарии покрыты `test_send_marks_blocked_on_forbidden` и `test_run_skips_users_who_blocked_bot`.

- [ ] **Step 6: Все тесты проходят**

Run: `.venv/bin/python -m pytest -q`
Expected: все passed. Возможные точки: `tests/test_handlers.py::test_admin_broadcast_button_enters_fsm_state` — должен остаться зелёным (рассылка не идёт); `tests/test_icons.py` инвентарь — новых эмодзи нет.

- [ ] **Step 7: `just check` и commit**

```bash
git add app/keyboards/admin.py app/handlers/admin/admin.py app/services/broadcast.py app/services/__init__.py tests/harness.py tests/test_broadcast.py tests/test_bot_blocked.py tests/test_handlers.py tests/test_custom_emoji.py
git commit -m "feat(broadcast): фоновый запуск из админки, стоп/обновить, строка в /admin, Message в FSM как JSON"
```

---

### Task 6: Жизненный цикл в `main.py` и сквозной тест с иконками

**Files:**
- Modify: `app/main.py` (`on_startup`, `on_shutdown`)
- Test: `tests/test_broadcast.py`

- [ ] **Step 1: Сквозной тест — эмодзи в тексте рассылки становятся иконками**

Добавить в конец `tests/test_broadcast.py`:

```python
# --- сквозной: CustomEmojiMiddleware конвертирует эмодзи в тексте рассылки ------


async def test_broadcast_text_gets_custom_emoji_icons(harness, admin, fake_db, fresh_broadcast, monkeypatch):
    harness.premium("on")
    await fake_db.add_user(1)
    await _arm_confirm_state(harness, admin, text="📤 Новости")
    monkeypatch.setattr(broadcast_module.settings, "broadcast_rate_limit_rps", 1000)

    await harness.send_callback("broadcast_confirm_yes", admin)
    await fresh_broadcast.wait(timeout=1)
    await _drain_handler_watchers()

    delivered = next(c for c in harness.calls if isinstance(c, SendMessage) and c.chat_id == 1)
    assert "<tg-emoji" in delivered.text and "Новости" in delivered.text
    assert delivered.parse_mode == "HTML"
    assert fake_db.broadcasts[1].status == "done"
```

Run: `.venv/bin/python -m pytest tests/test_broadcast.py -k custom_emoji_icons -v`
Expected: PASS уже сейчас (middleware подключён в харнесе). Если FAIL с обычным «📤» в тексте — значит `build_send_method` оставил `entities`/`parse_mode`, чинить там.

- [ ] **Step 2: `main.py`**

В `app/main.py`:

Импорт: после `from app.services.liveness import liveness` добавить `from app.services.broadcast import broadcast`.

В `on_startup` заменить блок с `liveness.configure(bot)` на:

```python
    # Проверка живых пользователей: ручной запуск из /admin и ночной автопрогон
    liveness.configure(bot)
    # Рассылка, прерванная рестартом, продолжается с курсора — ДО планировщика liveness,
    # иначе ночной автопрогон может занять слот и рассылка останется ждать следующего рестарта
    broadcast.configure(bot)
    await broadcast.resume_pending()
    if settings.liveness_check_interval_days > 0:
        _liveness_scheduler_task = asyncio.create_task(liveness.run_scheduler(), name="liveness-scheduler")
```

В `on_shutdown` перед блоком liveness добавить:

```python
    # Рассылку прерываем без stop(): статус в БД остаётся running, после рестарта продолжится с курсора
    if broadcast.stop_for_shutdown():
        await broadcast.wait(timeout=10)
```

- [ ] **Step 3: Проверка импортов и `just check`**

Run: `.venv/bin/python -c "import app.main"` — Expected: без ошибок (нет циклического импорта).
Run: `just check` — Expected: зелёный.

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_broadcast.py
git commit -m "feat(broadcast): возобновление после рестарта и корректное выключение в main.py"
```

---

### Task 7: Документация

**Files:**
- Modify: `AGENTS.md` (таблица §1 строка «Сервисы»; §4 — новый рецепт после 4.13; §5 — пункт про цикл отправки)
- Modify: `README.md` (§«Возможности админа», §«Как использовать», §«Конфигурация»)
- Modify: `.env.example` (**только append**, не читать)

- [ ] **Step 1: `AGENTS.md`**

В таблице §1 заменить строку «Сервисы» на:

```
| Сервисы | `app/services/` | Логика, не зависящая от aiogram: `broadcast.py` (рассылка: фон, курсор по id, чекпоинты в `broadcasts`, возобновление после рестарта; `ProgressReporter`), `liveness.py` (проверка живых + ночной планировщик), `admins.py` (`notify_admins`) |
```

После §4.13 добавить:

```markdown
### 4.14 Массовая отправка (рассылка)

Рассылка (`app/services/broadcast.py`, синглтон `broadcast`) — образец любой массовой отправки:

- получатели читаются курсором по `users.id` (`db.get_alive_user_ids(after_id, limit)`), не `get_alive_users()` целиком;
- отправка последовательная с ровным темпом `BROADCAST_RATE_LIMIT_RPS` (по умолчанию 20/с; Telegram даёт ~30/с
  суммарно, остаток — на обычные ответы бота);
- на 429 (`TelegramRetryAfter`) ждём **весь** `retry_after` — поток один, пауза глобальная;
- каждые 50 отправок курсор и счётчики пишутся в `broadcasts`; при старте бота `broadcast.resume_pending()`
  продолжает незавершённую рассылку (`status=running`), итог уходит админам через `notify_admins`;
- одновременно идёт не больше одной рассылки, и не вместе с проверкой живых (`liveness`).

Контент хранится как `Message.model_dump_json()` и отправляется через `Message.send_copy()`; текст/подпись
подменяются на `html_text` без `entities`, чтобы `CustomEmojiMiddleware` превратил эмодзи в иконки (§4.13).
В FSM-состояние кладётся **строка JSON**, не объект `Message` — `RedisStorage` хранит данные через `json.dumps`.

Нужна своя массовая отправка (например, уведомление сегменту)? Не пиши цикл `bot.send_*` по всем пользователям —
сделай запись в `broadcasts` и вызови `broadcast.start(id)`, либо повтори тот же паттерн: курсор + темп +
честный `retry_after` + чекпоинты.
```

В §4.12 фразу «403 при рассылке (`BroadcastService`)» заменить на «403 при рассылке (`broadcast`, §4.14)».

В §5 заменить пункт «Не отправлять сообщения в цикле без задержек…» на:

```
- Не отправлять сообщения в цикле по всем пользователям через `bot.send_*`: Telegram ограничивает ~30 сообщений/сек и банит за всплески. Рассылка — только через `broadcast` (§4.14).
```

- [ ] **Step 2: `README.md`**

В «Возможности админа» заменить пункты «📤 Система рассылок», «📈 Прогресс рассылки», «📋 Итоговая статистика» на:

```markdown
- **📤 Рассылки**: сообщение любого типа всем живым пользователям; идёт в фоне с ровным темпом
  (`BROADCAST_RATE_LIMIT_RPS`, по умолчанию 20/с — Telegram не банит), с кнопками «⏹ Остановить» и «🔄 Обновить»
- **♻️ Устойчивость рассылки**: прогресс сохраняется в БД каждые 50 отправок; после рестарта бота (деплой,
  падение) рассылка продолжается с места остановки, итог приходит всем админам
- **📋 Итоговая статистика**: доставлено, ошибок, заблокировали бота, успешность, длительность
```

(Если `♻️` нет в `SUPPORTED_EMOJI` — README не UI, инвентарный тест его не сканирует; но для единообразия можно взять `🔄`.)

В «Как использовать» пункт 5 заменить на: `5. **Подтвердите отправку** - рассылка пойдёт в фоне; прогресс в том же сообщении, «⏹ Остановить» в любой момент; `/admin` показывает текущую или последнюю рассылку`.

В блок `.env` конфигурации после `CUSTOM_EMOJI=auto` добавить:

```env

# Рассылка: сообщений в секунду (Telegram допускает ~30/с суммарно; 150 000 получателей при 20/с ≈ 2 ч)
BROADCAST_RATE_LIMIT_RPS=20
```

- [ ] **Step 3: `.env.example` — только дописать**

```bash
printf '\n# Рассылка: сообщений в секунду (Telegram допускает ~30/с суммарно, остаток — на обычные ответы)\nBROADCAST_RATE_LIMIT_RPS=20\n' >> .env.example
tail -3 .env.example
```

Expected: последние три строки — пустая, комментарий, `BROADCAST_RATE_LIMIT_RPS=20`.

- [ ] **Step 4: `just check` и commit**

```bash
git add AGENTS.md README.md .env.example
git commit -m "docs(broadcast): рецепт массовой отправки, BROADCAST_RATE_LIMIT_RPS, описание устойчивой рассылки"
```
