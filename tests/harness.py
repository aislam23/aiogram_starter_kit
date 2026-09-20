"""
Тестовый харнес: запуск хендлеров без Telegram, Docker, Postgres и Redis.

Как пользоваться:

    async def test_start(harness):
        sent = await harness.send_message("/start")
        assert "Привет" in sent[0].text

`harness.send_message` / `harness.send_callback` прогоняют апдейт через настоящий Dispatcher
с настоящими middleware и роутерами. Все вызовы Telegram API перехватываются `FakeSession`
и складываются в `harness.calls`; ответы бота (SendMessage, EditMessageText, ...) доступны
как список `harness.sent`.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, AsyncGenerator, Callable, List, Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    GetMe,
    SendMessage,
    TelegramMethod,
)
from aiogram.methods.base import TelegramType
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberBanned,
    ChatMemberMember,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    Message,
    MessageEntity,
    TelegramObject,
    Update,
    User,
)

from app.handlers import setup_routers
from app.middlewares import setup_middlewares
from app.middlewares.custom_emoji import CustomEmojiMiddleware, CustomEmojiStatus, custom_emoji_status

BOT_USER = User(id=42, is_bot=True, first_name="TestBot", username="test_bot")

_TG_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="(\d+)">')


def custom_emoji_entities(text: Optional[str]) -> Optional[List[MessageEntity]]:
    """Как Telegram: по одной custom_emoji entity на каждый <tg-emoji> в тексте.

    offset/length фиктивные — middleware проверяет только `type`.
    """
    if not text:
        return None
    entities = [
        MessageEntity(type="custom_emoji", offset=i, length=2, custom_emoji_id=m.group(1))
        for i, m in enumerate(_TG_EMOJI_RE.finditer(text))
    ]
    return entities or None


class FakeSession(BaseSession):
    """Сессия, которая не ходит в сеть: запоминает вызовы и отдаёт правдоподобные ответы."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: List[TelegramMethod[Any]] = []
        self._message_id = 1000
        # Режим custom emoji: отдавать ли custom_emoji entities за <tg-emoji> в тексте (Premium активен)
        self.premium_entities = False
        # Хук отказа: функция(method) -> исключение или None; None — запрос проходит.
        # Отвергнутые вызовы в `calls`/`sent` не попадают
        self.reject: Optional[Callable[[TelegramMethod[Any]], Optional[Exception]]] = None

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:  # pragma: no cover
        yield b""

    async def make_request(
        self, bot: Bot, method: TelegramMethod[TelegramType], timeout: Optional[int] = None
    ) -> TelegramType:
        if self.reject is not None:
            exc = self.reject(method)
            if exc is not None:
                raise exc
        self.calls.append(method)
        result = self._fake_response(method)
        # Реальный aiogram привязывает объекты ответа к боту, чтобы работали
        # `message.edit_text()` / `message.answer()` на результате вызова
        if isinstance(result, TelegramObject):
            result = result.as_(bot)
        return result

    def _fake_response(self, method: TelegramMethod[Any]) -> Any:
        if isinstance(method, GetMe):
            return BOT_USER
        if isinstance(method, SendMessage):
            self._message_id += 1
            return Message(
                message_id=self._message_id,
                date=datetime.now(UTC),
                chat=Chat(id=method.chat_id, type="private"),
                from_user=BOT_USER,
                text=method.text,
                entities=custom_emoji_entities(method.text) if self.premium_entities else None,
                # В Message.reply_markup Telegram кладёт только inline-клавиатуру
                reply_markup=method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None,
            )
        if isinstance(method, (EditMessageText, EditMessageReplyMarkup)):
            return Message(
                message_id=method.message_id or 0,
                date=datetime.now(UTC),
                chat=Chat(id=method.chat_id or 0, type="private"),
                from_user=BOT_USER,
                text=getattr(method, "text", None),
                entities=custom_emoji_entities(getattr(method, "text", None)) if self.premium_entities else None,
                reply_markup=method.reply_markup,
            )
        if hasattr(method, "caption"):
            # Медиа с подписью (SendPhoto, SendDocument, ...): нужно для детекции по caption_entities
            self._message_id += 1
            return Message(
                message_id=self._message_id,
                date=datetime.now(UTC),
                chat=Chat(id=getattr(method, "chat_id", None) or 0, type="private"),
                from_user=BOT_USER,
                caption=method.caption,
                caption_entities=custom_emoji_entities(method.caption) if self.premium_entities else None,
                reply_markup=method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None,
            )
        if isinstance(method, AnswerCallbackQuery):
            return True
        return True


def make_user(user_id: int = 1, first_name: str = "Тест", username: str = "tester") -> User:
    return User(id=user_id, is_bot=False, first_name=first_name, username=username)


class BotHarness:
    """Обёртка над Dispatcher + Bot с фейковой сессией."""

    def __init__(self) -> None:
        self.session = FakeSession()
        self.bot = Bot(
            token="42:TEST_TOKEN_FOR_TESTS_ONLY",
            session=self.session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.bot.session.middleware(CustomEmojiMiddleware())
        self.dp = Dispatcher(storage=MemoryStorage())
        setup_middlewares(self.dp)
        setup_routers(self.dp)
        self._update_id = 0
        self._message_id = 0

    # ── исходящие ────────────────────────────────────────────────

    @property
    def calls(self) -> List[TelegramMethod[Any]]:
        return self.session.calls

    @property
    def sent(self) -> List[TelegramMethod[Any]]:
        """Всё, что бот отправил или отредактировал в чате."""
        return [c for c in self.calls if isinstance(c, (SendMessage, EditMessageText))]

    @property
    def last_text(self) -> str:
        return self.sent[-1].text if self.sent else ""

    def clear(self) -> None:
        self.session.calls.clear()

    def reset(self) -> None:
        """Сброс между тестами: исходящие вызовы и FSM-состояния всех пользователей."""
        self.clear()
        self.dp.storage.storage.clear()  # MemoryStorage
        self.session.reject = None
        self.premium("off")

    def premium(self, mode: str) -> None:
        """Режим custom emoji.

        "off" — статус выключен заранее, конвертации нет (по умолчанию и после reset());
        "on"  — Premium активен: иконки конвертируются, сессия отдаёт custom_emoji entities;
        "lost" — статус включён, но entities не приходят (Premium закончился) — для теста детекции.
        """
        if mode not in ("off", "on", "lost"):
            raise ValueError(mode)
        custom_emoji_status.reset()
        self.session.premium_entities = mode == "on"
        if mode == "off":
            custom_emoji_status.disabled_at = datetime.now(UTC)

    @property
    def custom_emoji(self) -> CustomEmojiStatus:
        """Состояние custom emoji (для проверок в тестах)"""
        return custom_emoji_status

    # ── входящие ─────────────────────────────────────────────────

    def _next_ids(self) -> tuple[int, int]:
        self._update_id += 1
        self._message_id += 1
        return self._update_id, self._message_id

    async def send_message(self, text: str, user: Optional[User] = None) -> List[TelegramMethod[Any]]:
        """Пользователь отправил текст. Возвращает ответы бота на этот апдейт."""
        user = user or make_user()
        update_id, message_id = self._next_ids()
        before = len(self.calls)
        update = Update(
            update_id=update_id,
            message=Message(
                message_id=message_id,
                date=datetime.now(UTC),
                chat=Chat(id=user.id, type="private", first_name=user.first_name),
                from_user=user,
                text=text,
            ),
        )
        await self.dp.feed_update(self.bot, update)
        return [c for c in self.calls[before:] if isinstance(c, (SendMessage, EditMessageText))]

    async def send_callback(
        self, data: str, user: Optional[User] = None, message_text: str = "…"
    ) -> List[TelegramMethod[Any]]:
        """Пользователь нажал inline-кнопку. Возвращает ответы бота на этот апдейт."""
        user = user or make_user()
        update_id, message_id = self._next_ids()
        before = len(self.calls)
        update = Update(
            update_id=update_id,
            callback_query=CallbackQuery(
                id=str(update_id),
                from_user=user,
                chat_instance="test",
                data=data,
                message=Message(
                    message_id=message_id,
                    date=datetime.now(UTC),
                    chat=Chat(id=user.id, type="private", first_name=user.first_name),
                    from_user=BOT_USER,
                    text=message_text,
                ),
            ),
        )
        await self.dp.feed_update(self.bot, update)
        return [c for c in self.calls[before:] if isinstance(c, (SendMessage, EditMessageText))]

    async def send_users_shared(
        self, shared: List[dict], user: Optional[User] = None, request_id: int = 1
    ) -> List[TelegramMethod[Any]]:
        """Пользователь выбрал людей через кнопку request_users. shared: [{"user_id":..., "first_name":..., "username":...}]"""
        from aiogram.types import SharedUser, UsersShared

        user = user or make_user()
        update_id, message_id = self._next_ids()
        before = len(self.calls)
        update = Update(
            update_id=update_id,
            message=Message(
                message_id=message_id,
                date=datetime.now(UTC),
                chat=Chat(id=user.id, type="private", first_name=user.first_name),
                from_user=user,
                users_shared=UsersShared(request_id=request_id, users=[SharedUser(**item) for item in shared]),
            ),
        )
        await self.dp.feed_update(self.bot, update)
        return [c for c in self.calls[before:] if isinstance(c, (SendMessage, EditMessageText))]

    async def send_my_chat_member(self, user: Optional[User] = None, blocked: bool = True) -> None:
        """Пользователь заблокировал (blocked=True) или разблокировал бота в личном чате."""
        user = user or make_user()
        update_id, _ = self._next_ids()
        member = ChatMemberMember(user=BOT_USER)
        banned = ChatMemberBanned(user=BOT_USER, until_date=datetime.fromtimestamp(0, UTC))
        update = Update(
            update_id=update_id,
            my_chat_member=ChatMemberUpdated(
                chat=Chat(id=user.id, type="private", first_name=user.first_name),
                from_user=user,
                date=datetime.now(UTC),
                old_chat_member=member if blocked else banned,
                new_chat_member=banned if blocked else member,
            ),
        )
        await self.dp.feed_update(self.bot, update)

    async def state_of(self, user: Optional[User] = None) -> Optional[str]:
        """Текущее FSM-состояние пользователя."""
        user = user or make_user()
        ctx = self.dp.fsm.get_context(self.bot, chat_id=user.id, user_id=user.id)
        return await ctx.get_state()


def buttons_of(method: TelegramMethod[Any]) -> List[str]:
    """Тексты inline-кнопок из отправленного сообщения."""
    markup = getattr(method, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return []
    return [btn.text for row in markup.inline_keyboard for btn in row]


def callbacks_of(method: TelegramMethod[Any]) -> List[str]:
    """callback_data inline-кнопок из отправленного сообщения."""
    markup = getattr(method, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return []
    return [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]
