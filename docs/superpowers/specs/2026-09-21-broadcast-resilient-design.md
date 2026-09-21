# Рассылка, устойчивая к большой базе и рестартам — дизайн

**Дата:** 2026-09-21
**Статус:** утверждён пользователем, ждёт плана

## Проблема

Текущая рассылка (`app/services/broadcast.py`, `confirm_broadcast` в `app/handlers/admin/admin.py`)
на базе в десятки–сотни тысяч пользователей:

1. `db.get_alive_users()` загружает всех получателей в память как ORM-объекты.
2. Отправляет всплесками: `asyncio.gather` по 30 запросов, потом пауза 1 с. Telegram допускает
   ~30 сообщений/с ровным потоком; всплески чаще получают 429.
3. Flood-wait (`TelegramRetryAfter`) обрабатывается на одного получателя: спит одна корутина,
   остальные 29 и следующие пачки продолжают слать — это продлевает бан.
4. Выполняется прямо в хендлере: нельзя остановить, нет защиты от параллельного второго запуска
   (двойная нагрузка), при рестарте бота теряется без следа.
5. Отправляет `text=message.text` с `parse_mode=HTML`: форматирование админа теряется,
   символ `<` в тексте ломает отправку.
6. `receive_broadcast_message` кладёт в FSM-состояние объект `Message`. `RedisStorage.set_data`
   делает `json.dumps` → `TypeError: Object of type Message is not JSON serializable`. В проде
   (`RedisStorage`) мастер рассылки падает ещё до подтверждения; тесты этого не видят, потому что
   харнесс работает на `MemoryStorage`.

## Цели

1. Рассылка на 150 000 пользователей проходит без бана: ровный темп ниже лимита Telegram,
   один поток, честное ожидание `retry_after`.
2. Постоянное потребление памяти: получатели читаются курсором по id.
3. Рассылка идёт в фоне, её можно остановить из админки, одновременно идёт не больше одной
   (и не одновременно с проверкой живых).
4. Рестарт бота (деплой, падение) не теряет рассылку: она возобновляется с сохранённого курсора.
5. Форматирование и тип сообщения админа сохраняются; эмодзи в тексте проходят через
   `CustomEmojiMiddleware` и становятся иконками.

## Не цели

- Журнал доставки по каждому получателю (outbox) — избыточно для шаблона.
- Внешняя очередь/воркер (arq, celery).
- Возобновление обновления *сообщения прогресса* после рестарта: id сообщения не храним,
  итог возобновлённой рассылки уходит всем админам через `notify_admins`.
- «Продолжить» для остановленной вручную рассылки: `stopped` — финальный статус.
- Планирование рассылок на будущее и растягивание на 8–12 ч.
- Адаптивное снижение темпа после 429: темп фиксирован настройкой, 429 обрабатывается ожиданием.

## Лимиты Telegram, на которые опираемся

- Массовые уведомления: не больше ~30 сообщений/с суммарно по всем чатам. Превышение —
  `429 Too Many Requests` с `retry_after`; повторные нарушения продлевают ожидание.
- Один чат: не чаще 1 сообщения/с (для рассылки не актуально — каждому по одному).
- Пока идёт рассылка на 20/с, на обычные ответы бота остаётся ~10/с из общего лимита.

## Компоненты

| Файл | Изменение |
|---|---|
| `app/database/models.py` | новая модель `Broadcast` |
| `app/database/migrations/versions/20260921_000001_add_broadcasts.py` | таблица `broadcasts` |
| `app/database/database.py` | `create_broadcast`, `get_broadcast`, `get_running_broadcast`, `get_last_broadcast`, `update_broadcast`, `get_alive_user_ids` |
| `app/config.py` | `broadcast_rate_limit_rps: int = 20` (`BROADCAST_RATE_LIMIT_RPS`) |
| `app/services/broadcast.py` | `BroadcastService` переписан: синглтон `broadcast`, фоновая задача, курсор, чекпоинты, возобновление; `ProgressReporter` без изменений |
| `app/services/liveness.py` | `start()` отказывает при идущей рассылке; планировщик пропускает тик |
| `app/services/__init__.py` | экспорт `broadcast` |
| `app/handlers/admin/admin.py` | `receive_broadcast_message` кладёт в state `message.model_dump_json()` (строку), а не объект; `confirm_broadcast` запускает фон и сразу выходит; колбэки `broadcast:stop/refresh/back`; строка рассылки в `/admin`; `admin_broadcast` при идущей рассылке открывает экран прогресса |
| `app/keyboards/admin.py` | `broadcast_running()`, `broadcast_done()` |
| `app/main.py` | `broadcast.configure(bot)` + `resume_pending()` в `on_startup`; `stop()` + `wait()` в `on_shutdown` |
| `tests/conftest.py` | `FakeDb`: хранилище рассылок и `get_alive_user_ids` |
| `tests/test_broadcast.py` | тесты сервиса и хендлеров (старые `_send_single_message*` заменяются) |
| `AGENTS.md`, `README.md`, `.env.example` | описание, `BROADCAST_RATE_LIMIT_RPS`, правило для агента |

## Хранение

### Модель `Broadcast` (таблица `broadcasts`)

| Поле | Тип | Назначение |
|---|---|---|
| `id` | SERIAL PK | номер рассылки |
| `status` | VARCHAR(20) NOT NULL | `running` / `done` / `stopped` / `failed` |
| `created_by` | BIGINT NOT NULL | user_id админа, запустившего рассылку |
| `content` | TEXT NOT NULL | `Message.model_dump_json()` исходного сообщения админа |
| `button_text` | VARCHAR(255) NULL | текст кнопки под сообщением |
| `button_url` | VARCHAR(2048) NULL | ссылка кнопки |
| `total` | INTEGER NOT NULL DEFAULT 0 | получателей на момент старта (`get_alive_users_count`) |
| `last_user_id` | BIGINT NOT NULL DEFAULT 0 | курсор: последний обработанный `users.id` |
| `sent`, `failed`, `blocked` | INTEGER NOT NULL DEFAULT 0 | счётчики |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | старт |
| `finished_at` | TIMESTAMPTZ NULL | конец (любой финальный статус) |

Миграция — по образцу `20260911_000001_add_bot_blocked_and_liveness.py`: `check_can_apply`
через `information_schema.tables`, `CREATE TABLE IF NOT EXISTS`, `downgrade` — `DROP TABLE`.

Почему JSON сообщения, а не `chat_id + message_id` для `copy_message`: если админ удалит
исходное сообщение, рассылка после рестарта всё равно продолжится; восстановленный `Message`
отправляется через `send_copy` без обращения к Telegram. Объём — единицы килобайт на рассылку.

### Методы `db`

- `create_broadcast(created_by, content, button_text, button_url, total) -> int`
- `get_broadcast(id) -> Optional[Broadcast]`
- `get_running_broadcast() -> Optional[Broadcast]` — `status='running'`, самая новая
  (инвариант: не больше одной).
- `get_last_broadcast() -> Optional[Broadcast]` — для панели `/admin`.
- `update_broadcast(id, *, last_user_id, sent, failed, blocked, status=None)` — при финальном
  статусе (`done`/`stopped`/`failed`) проставляет `finished_at`.
- `get_alive_user_ids(after_id, limit) -> List[int]` — курсор `WHERE *_alive_clause() AND id > after_id
  ORDER BY id LIMIT limit`. Тот же `_alive_clause()`, что у `get_alive_users`/`get_alive_users_count`.

## Сервис `app/services/broadcast.py`

По образцу `LivenessService`: синглтон `broadcast = BroadcastService()`, `configure(bot)`.

### Константы и настройка

```python
BATCH_SIZE = 500            # id получателей на один запрос к БД
CHECKPOINT_EVERY = 50       # отправок между записями курсора в БД
PROGRESS_EVERY_SECONDS = 5  # не чаще — колбэк прогресса (редактирует сообщение админа)
MAX_RETRIES = 3             # попыток отправки одному получателю всего (как в liveness), не повторов
```

`settings.broadcast_rate_limit_rps` (`BROADCAST_RATE_LIMIT_RPS`, по умолчанию 20) — рядом с
`liveness_rate_limit_rps` в `app/config.py`. 150 000 / 20 ≈ 2 ч 5 мин.

### Состояние

```python
@dataclass
class BroadcastProgress:
    broadcast_id: int
    total: int
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    started_at: float = field(default_factory=time.monotonic)
    finished_at: Optional[float] = None
    status: str = "running"         # итоговый статус после завершения

    processed -> sent + failed + blocked
    percent   -> min(100, processed * 100 // total) если total, иначе 100
    elapsed   -> timedelta по monotonic
```

Поля сервиса: `bot`, `_task`, `progress: Optional[BroadcastProgress]`, `last_result`,
`_stop_requested: bool`, `_error_kinds: Counter`.

### Интерфейс

- `start(broadcast_id, progress_callback=None) -> Optional[asyncio.Task]` — `None`, если
  `self.is_running()` или `liveness.is_running()`. Создаёт задачу `broadcast-{id}`.
- `stop() -> bool` — ставит `_stop_requested = True`, отменяет задачу. Итоговый статус `stopped`.
- `stop_for_shutdown() -> bool` — отменяет задачу **без** `_stop_requested`: статус в БД остаётся
  `running`, рассылка возобновится после рестарта.
- `wait(timeout=None)` — `asyncio.wait({task}, timeout)` + `_log_outcome` (как в liveness).
- `is_running() -> bool` — задача жива или `progress is not None`.
- `resume_pending() -> None` — в `on_startup`: если `db.get_running_broadcast()` есть —
  `start(row.id)` и watcher, который по завершении шлёт итог всем админам через `notify_admins`.
  Если итог со статусом `running` (снова прервана рестартом) — ничего не шлём.
  Лог: `📤 Broadcast #N resumed at processed/total`. Если `start()` вернул `None` —
  `logger.warning` (строка останется `running` до следующего рестарта). Чтобы этого не случилось,
  `on_startup` вызывает `resume_pending()` **до** запуска планировщика liveness.
- `run(broadcast_id, progress_callback=None) -> BroadcastProgress` — цикл.

### Цикл `run`

```
row = await db.get_broadcast(broadcast_id)              # нет или не running → RuntimeError
progress = BroadcastProgress(id, total=row.total, sent=row.sent, failed=row.failed, blocked=row.blocked)
self.progress = progress; self.last_result = None; self._stop_requested = False
delay = 1 / max(settings.broadcast_rate_limit_rps, 1)
next_at = time.monotonic(); after_id = row.last_user_id; last_report = 0.0; since_checkpoint = 0

try:
    # Восстановление контента — внутри try: невалидный JSON должен закончиться status=failed,
    # иначе строка останется running и resume_pending() будет поднимать её на каждом рестарте
    message = Message.model_validate_json(row.content)
    keyboard = AdminKeyboards.create_custom_button(row.button_text, row.button_url) если оба есть
    while True:
        ids = await db.get_alive_user_ids(after_id, BATCH_SIZE)
        if not ids: break
        for uid in ids:
            await asyncio.sleep(max(0.0, next_at - time.monotonic()))     # темп задаём до запроса
            next_at = max(next_at, time.monotonic()) + delay
            verdict = await self._send(uid, message, keyboard)           # "sent" | "blocked" | "failed"
            progress.<verdict> += 1
            after_id = uid
            since_checkpoint += 1
            if since_checkpoint >= CHECKPOINT_EVERY:
                await self._checkpoint(progress, after_id); since_checkpoint = 0
            if progress_callback and monotonic() - last_report >= PROGRESS_EVERY_SECONDS:
                last_report = monotonic(); await progress_callback(progress)   # ошибки колбэка → debug
    progress.status = "done"
except asyncio.CancelledError:
    progress.status = "stopped" if self._stop_requested else "running"   # shutdown → останется running
    raise
except Exception:
    progress.status = "failed"; logger.exception(...); raise
finally:
    progress.finished_at = monotonic()
    await self._checkpoint(progress, after_id, status=progress.status)   # ошибки → logger.exception
    self.last_result = progress; self.progress = None
    лог итога с _errors_summary()
return progress
```

`_checkpoint(progress, after_id, status=None)` → `db.update_broadcast(id, last_user_id=after_id,
sent=…, failed=…, blocked=…, status=status)`. При `status="running"` (shutdown) `finished_at`
не проставляется — строка остаётся кандидатом на возобновление.

Возобновление начинается с `last_user_id` последнего чекпоинта: при `kill -9` до 50
получателей могут получить сообщение повторно. При штатном `SIGTERM` курсор точный.

### Отправка `_send(uid, message, keyboard) -> "sent" | "blocked" | "failed"`

```
method = message.send_copy(chat_id=uid, reply_markup=keyboard)
```

`send_copy` подбирает `Send*` по типу сообщения (текст, фото, видео, документ, аудио, голос,
кружок, анимация, стикер, опрос, контакт, локация…) и передаёт **явные entities**.
`CustomEmojiMiddleware` при явных entities текст не трогает, поэтому текст/подпись подменяем
на HTML, чтобы эмодзи стали иконками и форматирование сохранилось:

```
if isinstance(method, SendMessage):
    method = method.model_copy(update={"text": message.html_text, "entities": None, "parse_mode": "HTML"})
elif getattr(method, "caption", None) is not None:
    method = method.model_copy(update={"caption": message.html_text, "caption_entities": None, "parse_mode": "HTML"})
await self.bot(method)
```

`send_copy` у сообщения без `_bot` (восстановлено из JSON) возвращает метод — `await self.bot(method)`
не требует привязки. `TypeError` из `send_copy` (тип сообщения не поддерживается) в `_send` **не
ловится**: он одинаков для всех получателей, поэтому должен уронить всю рассылку в `failed` через
`except Exception` в `run`, а не дать 150 000 «failed» по темпу 20/с.

Ошибки (цикл `for _ in range(MAX_RETRIES)`):

| Исключение | Вердикт | Действие |
|---|---|---|
| `TelegramRetryAfter` | повтор | `logger.warning`, `sleep(retry_after)` **целиком, без кэпа** — урезать значит получить следующий 429 и продлить бан; исчерпаны `MAX_RETRIES` попыток → `failed`, `_error_kinds["RetryAfter:exhausted"]` |
| `TelegramForbiddenError` | `blocked` | `db.set_bot_blocked(uid, True)` (ошибка БД → warning) |
| `TelegramBadRequest` с «chat not found» / «user is deactivated» | `blocked` | то же — удалённый аккаунт |
| прочий `TelegramBadRequest` | `failed` | `_error_kinds["BadRequest:<40 симв.>"]`, `logger.debug` |
| `Exception` | `failed` | `_error_kinds[type name]`, `logger.debug` |

Поток один, поэтому ожидание `retry_after` останавливает всю рассылку — глобальный backoff
получается сам собой.

### Взаимоисключение с проверкой живых

- `broadcast.start()` → `None`, если `liveness.is_running()`.
- `liveness.start()` → `None`, если `broadcast.is_running()`; `_maybe_run_scheduled` пропускает тик.
- Импорт: `broadcast.py` импортирует `liveness`, а `liveness.py` — `broadcast` → циклический импорт.
  Решение: `liveness.py` импортирует `from app.services import broadcast as broadcast_module`
  лениво внутри функций **или** проверка вынесена в общий модуль. Выбор: в `app/services/liveness.py`
  импорт `from app.services.broadcast import broadcast` внутри `start()` и `_maybe_run_scheduled()`;
  в `broadcast.py` — обычный импорт `liveness` на уровне модуля.

## Админка

### Запуск (`confirm_broadcast`)

1. `is_admin` проверка как сейчас.
2. Если `broadcast.is_running()` → показать экран прогресса, `callback.answer("Рассылка уже идёт", show_alert=True)`, `state.clear()`, выход.
   Если `liveness.is_running()` → `callback.answer("Идёт проверка живых — дождитесь её окончания", show_alert=True)`, `state.clear()`, выход.
3. `content = data["broadcast_message"]` — уже строка JSON (см. ниже); `total = await db.get_alive_users_count()`.
4. `broadcast_id = await db.create_broadcast(created_by=callback.from_user.id, content=content, button_text, button_url, total)`.
5. `await callback.answer()`; `await state.clear()` — хендлер больше не ждёт конца рассылки.
6. `reporter = ProgressReporter(callback.message)`; экран «📤 <b>Рассылка…</b>\n\nЗапускаю…» с `broadcast_running()`.
7. `task = broadcast.start(broadcast_id, on_progress)`; `None` (гонка) → alert «Идёт проверка живых…», если `liveness.is_running()`, иначе «Рассылка уже идёт», и `db.update_broadcast(id, last_user_id=0, sent=0, failed=0, blocked=0, status="failed")`, чтобы строка не осталась `running`.
8. `watch()`-задача как в `liveness_confirm`: по завершении `reporter.finish(format_broadcast_result(result), broadcast_done())`; при исключении — «❌ Рассылка упала, подробности в логах». Если `result.status == "running"` (бот выключается) — ничего не редактировать: после рестарта итог придёт через `resume_pending`.

### Мастер создания (`receive_broadcast_message`)

В state кладём `broadcast_message=message.model_dump_json()` — строку. `RedisStorage` хранит
данные через `json.dumps`, объект `Message` туда не помещается (баг №6). Превью «получателей: N»
и остальные шаги мастера не меняются. Тест харнеса на этот шаг проверяет, что значение в state —
`str` (иначе `MemoryStorage` в тестах снова скроет проблему).

### Колбэки

- `broadcast:stop` — `broadcast.stop()` → «Останавливаю…» / «Рассылка не идёт».
- `broadcast:refresh` — экран прогресса или итог последней (`last_result`).
- `broadcast:back` — в панель `/admin`.
- `admin_broadcast` (кнопка «📤 Рассылка») при `broadcast.is_running()` открывает экран прогресса
  вместо мастера создания.

### Клавиатуры (`AdminKeyboards`)

- `broadcast_running()`: «⏹ Остановить» `broadcast:stop`, «🔄 Обновить» `broadcast:refresh`.
- `broadcast_done()`: «⬅️ Назад» `broadcast:back`.

### Панель `/admin`

Строка после «🕐 Последний запуск»:
- идёт: `📤 Рассылка: идёт <b>12 340 / 150 000</b> (8%)`
- нет: `📤 Последняя рассылка: <b>20.09 14:10</b> — завершена, 149 812 / 150 000` (дата — `finished_at`, статус по-русски: завершена / остановлена / упала; из `db.get_last_broadcast()`), или `📤 Рассылок ещё не было`.

### Тексты

- `format_broadcast_progress(progress)`: заголовок «📤 <b>Рассылка…</b>», `Отправлено X из N (P%)`,
  `✅ доставлено · ❌ ошибок · 🚫 заблокировали`, `⏱ elapsed`.
- `format_broadcast_result(result)`: заголовок по статусу — «✅ Рассылка завершена» / «⏹ Рассылка
  остановлена» / «❌ Рассылка упала»; получателей, доставлено, ошибок, заблокировали, успешность %,
  длительность; при `stopped` — «остановлена на X из N».

Эмодзи — только из `SUPPORTED_EMOJI` (`app/ui/icons.py`); `⏹` и `🔄` там уже есть (liveness).
Если новых эмодзи нет — инвентарный тест `tests/test_icons.py` остаётся зелёным.

## Жизненный цикл в `app/main.py`

- `on_startup`: после `liveness.configure(bot)` — `broadcast.configure(bot)`; `await broadcast.resume_pending()` — **до** `create_task(liveness.run_scheduler())`, иначе ночной автопрогон может занять слот.
- `on_shutdown`: до остановки liveness — `if broadcast.stop_for_shutdown(): await broadcast.wait(timeout=10)`.
  `stop_for_shutdown()` отменяет задачу **без** `_stop_requested`, чтобы статус остался `running`
  и рассылка возобновилась после рестарта. (Ручной `stop()` из админки ставит `stopped`.)

## Тестирование

### `tests/conftest.py` — `FakeDb`

`broadcasts: dict[int, Broadcast]`, `create_broadcast`, `get_broadcast`, `get_running_broadcast`,
`get_last_broadcast`, `update_broadcast` (финальный статус проставляет `finished_at`),
`get_alive_user_ids(after_id, limit)` — отсортированные id живых `> after_id`. Все — в список
`monkeypatch.setattr` фикстуры `fake_db`.

### `tests/test_broadcast.py` — сервис (через `FakeBot`, `no_sleep`)

`FakeBot` из текущих тестов расширяется: `__call__(method)` записывает метод, по сценарию
бросает `TelegramRetryAfter` / `TelegramForbiddenError` / `TelegramBadRequest`. Патч
`asyncio.sleep` в модуле `app.services.broadcast` записывает запрошенные интервалы.

1. Ровный темп: 5 получателей при rps=10 → **разности соседних** аргументов `sleep` ≈ 0.1 (при no-op `sleep` `monotonic` почти не растёт, поэтому аргументы кумулятивны: 0, 0.1, 0.2…), 5 методов отправлены по одному.
2. 429 → `sleep(retry_after)` без урезания, тот же получатель повторён, вердикт `sent`.
3. 429 на всех `MAX_RETRIES` попытках → `failed`, `_error_kinds["RetryAfter:exhausted"]`; `sleep` вызван с `retry_after` ровно `MAX_RETRIES` раз.
3a. `send_copy` бросает `TypeError` (неподдерживаемый тип) → `run` завершается `status="failed"` после первого получателя, остальные не трогаются.
4. `Forbidden` → `blocked`, `fake_db.calls` содержит `set_bot_blocked(uid, True)`.
5. `BadRequest("chat not found")` → `blocked`; другой `BadRequest` → `failed`.
6. Чекпоинт: 120 получателей → `update_broadcast` вызван на 50, 100 и в `finally` (120, `status="done"`).
7. `stop()` посреди рассылки → `status="stopped"`, `last_user_id` = последний обработанный, `finished_at` есть.
8. Отмена задачи без `stop()` (`stop_for_shutdown`) → в БД `status="running"`, `finished_at` нет.
9. `resume_pending()` при `running` с `last_user_id=3` из пяти пользователей → отправлено только 4 и 5; итог ушёл админам (`notify_admins` подменён).
10. `resume_pending()` без `running` → ничего не запущено.
11. `_send` для текста: метод `SendMessage` с `text == html_text`, `entities is None`, `parse_mode == "HTML"`; для фото с подписью — `caption` подменён; для стикера — без изменений.
12. `start()` при `liveness.is_running()` → `None`; `liveness.start()` при `broadcast.is_running()` → `None`.

### `tests/test_broadcast.py` — хендлеры (через `harness`)

13. Подтверждение: создана строка в `fake_db.broadcasts`, state очищен **до** окончания рассылки, экран «Запускаю…» показан, `callback.answer` вызван до отправки.
13a. `receive_broadcast_message`: `await state.get_data()` содержит `broadcast_message` типа `str`, и `Message.model_validate_json` его восстанавливает с тем же `text`.
13b. (блок сервиса) Невалидный `content` в строке `running` → `run` завершается с `status="failed"`, `finished_at` есть, `resume_pending()` на следующем вызове ничего не запускает.
14. Итог: после завершения фоновой задачи сообщение прогресса отредактировано в `format_broadcast_result`.
15. Повторное подтверждение при идущей рассылке → alert «Рассылка уже идёт», новая строка не создана.
16. `broadcast:stop` → задача отменена, итог «остановлена».
17. `/admin` во время рассылки показывает строку «идёт X / N».
18. Эмодзи в тексте рассылки через harness с `premium("on")` → в `harness.sent` текст содержит `<tg-emoji>` (сквозная проверка с `CustomEmojiMiddleware`).

Старые тесты `test_send_single_message_retries_after_flood_wait` и
`test_send_single_message_gives_up_after_max_retries` удаляются (покрыты №2–3).
Тесты `ProgressReporter` не меняются.

## Документация

- `AGENTS.md`: в таблицу компонентов — «Рассылка: фоновая, курсор, чекпоинты, возобновление»;
  в §4 рецепт «Массовая отправка»: **никогда не звать `bot.send_*` в цикле по всем пользователям —
  использовать `broadcast`** (или тот же паттерн: курсор + ровный темп + честный `retry_after`);
  `BROADCAST_RATE_LIMIT_RPS` в таблицу настроек.
- `README.md`: раздел «📤 Рассылка» — что происходит при 429, рестарте, как остановить;
  `BROADCAST_RATE_LIMIT_RPS=20` в конфигурации.
- `.env.example`: append `BROADCAST_RATE_LIMIT_RPS=20` с комментарием (файл не читать — только дописать).

## Риски и допущения

- Курсор по `users.id` предполагает, что новые пользователи, появившиеся во время рассылки,
  получат сообщение, если их id больше курсора (Telegram id не монотонны по времени — это
  допустимо: часть новых получит, часть нет).
- `Message.model_validate_json` при обновлении aiogram: старые JSON в `broadcasts.content`
  могут не провалидироваться → `failed` с логом (разбор внутри `try`); на новые рассылки не влияет.
- Дубликаты до `CHECKPOINT_EVERY` получателей при аварийном завершении процесса — принято.
- Один процесс бота: две реплики запустят одну рассылку дважды. Шаблон рассчитан на один инстанс.
