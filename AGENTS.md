# AGENTS.md — плейбук для AI-агентов

Этот файл читают Claude Code, Codex, Cursor и другие агенты. Он описывает, как из этого шаблона
собрать Telegram-бота **без участия человека в терминале**, и какие правила нельзя нарушать.
`CLAUDE.md` ссылается сюда.

## 0. Главные правила

1. **Секреты не проходят через чат.** Никогда не проси пользователя вставить токен бота, IP-адрес сервера,
   пароль или ключ в диалог. Токен ставится командой `just set-token` (см. §2), сервер — `just set-server` (см. §6).
   Файлы `.env*` и папку `.deploy/` не читай и не печатай: в `.claude/settings.json` они запрещены к чтению намеренно.
2. **Проверяй, а не предполагай.** После каждого изменения кода: `just check` (линтер + тесты + сканер секретов,
   Docker не нужен). Перед запуском: `just doctor --json`. После запуска: `just logs-json`.
3. **Одна задача — один рецепт из §4.** Не изобретай структуру, копируй паттерн из существующего файла.
4. **Язык.** Комментарии, docstring и сообщения бота — на русском. Идентификаторы — на английском.
5. **Ничего не удаляй из `.env` и не переименовывай папку проекта.** Не трогай git-историю без явной просьбы.

## 1. Что здесь есть

| Слой | Где | Зачем |
|---|---|---|
| Точка входа | `app/main.py` | Bot + Dispatcher, middleware, роутеры, миграции при старте, polling |
| Настройки | `app/config.py` → `settings` | Pydantic Settings из `.env`; `settings.is_admin(id)` |
| Хендлеры | `app/handlers/` | Один файл = один `Router`; регистрация в `app/handlers/__init__.py` |
| Статус бота у пользователя | `app/handlers/chat_member.py` | `my_chat_member` в личке → `users.bot_blocked` (заблокировал / разблокировал бота) |
| Примеры | `app/handlers/examples/` | FSM-анкета `/survey`, пагинация `/items`. Включаются `EXAMPLE_HANDLERS=true` |
| Админка | `app/handlers/admin/` | `/admin`, управление админами (`admins.py`), рассылки, настройки API |
| Фильтры | `app/filters/` | `IsAdmin()` в декораторе; внутри хендлера доступен аргумент `is_admin: bool` из middleware |
| Middleware | `app/middlewares/` | Логирование, автосохранение пользователей, распознавание админов по username (outer) |
| FSM | `app/states/` | `StatesGroup` для многошаговых сценариев; хранилище — Redis |
| Клавиатуры | `app/keyboards/` | Inline-клавиатуры через `InlineKeyboardBuilder` |
| Сервисы | `app/services/` | Логика, не зависящая от aiogram: `broadcast.py` (рассылка, `ProgressReporter`), `liveness.py` (проверка живых пользователей + ночной планировщик) |
| БД | `app/database/` | SQLAlchemy async + asyncpg; `db` — синглтон с методами |
| Миграции | `app/database/migrations/versions/` | Свои классы `Migration`, применяются при старте |
| Логи | `logs/bot.jsonl` | JSON Lines, секреты замаскированы |
| Тесты | `tests/` | Харнес без Telegram и Docker (`tests/harness.py`) |
| Скрипты | `scripts/` | `init_project.py`, `set_token.py`, `doctor.py`, `check_secrets.py` |
| Деплой | `scripts/` | `providers.py` (где арендовать), `set_server.py` (подключить сервер), `remote_deploy.py` (деплой по SSH), `github_secrets.py` (секреты в GitHub) |

Стек: Python 3.11, aiogram 3.20, PostgreSQL 15, Redis 7, Docker Compose. Parse mode по умолчанию — HTML.

## 2. Сценарий «новый бот с нуля»

```bash
git clone <шаблон> my_bot && cd my_bot
just venv                                    # локальное окружение для проверок (один раз)
just init my_bot @artem "Бот для заметок"    # админ: @username или Telegram ID; без диалогов
just set-token                               # ← человек вставляет токен сам, агент видит только «@bot подключён»
just doctor                                  # Docker, .env, токен, админы
just check                                   # линтер + тесты + секреты
just dev-d                                   # запуск
just logs-json 30                            # убедиться, что бот стартовал
```

Что сказать человеку перед `just set-token` (дословно, без слова «env»):

> Откройте в Telegram @BotFather, отправьте /newbot, ответьте на два вопроса и **скопируйте токен**
> из последнего сообщения. Больше ничего делать не нужно — я заберу его из буфера обмена.
> Если не получится, откроется страница с одним полем: вставьте туда и нажмите «Сохранить».
> Токен никогда не вставляйте в чат со мной. Если вставили случайно — в @BotFather нажмите /revoke.

Не запускай `make init-project` / `just init-project` / `scripts/init-project.sh`: это мастер для людей, он ждёт ввода
в терминале, включая токен, и может переименовать папку проекта. Для агента только `just init` + `just set-token`.

`just init` не спрашивает ничего: имя проекта и username — не секреты, их можно спросить в чате.
**Спрашивай у человека username** (он его знает), а не Telegram ID (его почти никто не знает).
Бот сам узнает ID, когда этот человек первый раз ему напишет, и запомнит его в базе как администратора
(`ADMIN_USERNAMES` в `.env`, механика в `app/middlewares/user.py`). Если человек знает ID — можно и ID.
После запуска попроси его отправить боту `/start`, затем `/admin`.

Как понять, что бот работает, не заглядывая в Telegram: в `logs/bot.jsonl` появится запись
`Bot @имя started successfully`, а после `/start` от пользователя — запись `Message from <id>`.

## 3. Как проверять

| Команда | Что делает | Нужен Docker |
|---|---|---|
| `just check` | ruff + pytest + сканер секретов | нет |
| `just test tests/test_x.py -k name` | точечный запуск тестов | нет |
| `just doctor [--json] [--offline]` | окружение: Docker, `.env`, формат токена, getMe, админы | нет |
| `just dev-d` / `just stop` | запуск/остановка всех сервисов | да |
| `just logs-json [N]` | последние N строк JSON-логов | нет |
| `just server-logs [N]` / `just server-status` | логи и статус бота на сервере по SSH | нет |
| `just logs-bot` | живые логи контейнера | да |
| `just db-shell` | psql внутри контейнера | да |

Тест хендлера пишется так (`tests/harness.py` делает всё остальное):

```python
async def test_hello(harness, user):
    replies = await harness.send_message("/hello", user)
    assert "Привет" in replies[0].text

async def test_button(harness, user):
    replies = await harness.send_callback("menu:settings", user)
    assert replies[0].__class__.__name__ == "EditMessageText"
    assert await harness.state_of(user) == "MyStates:step2"
```

`fake_db` (фикстура) подменяет методы `db` заглушкой в памяти. Если добавил метод в `Database`,
добавь его и в `FakeDb` в `tests/conftest.py`.

## 4. Рецепты

### 4.1 Новая команда

1. Создай `app/handlers/<name>.py` по образцу `app/handlers/help.py`: `router = Router(name="<name>")`,
   хендлер с `@router.message(Command("<cmd>"))`.
2. Зарегистрируй в `app/handlers/__init__.py` через `dp.include_router(...)`. Порядок важен:
   апдейт достаётся первому подошедшему роутеру. Общие команды — после админских.
3. Добавь команду в текст `/help` (`app/handlers/help.py`).
4. Тест в `tests/test_<name>.py`, затем `just check`.

### 4.2 Многошаговый сценарий (FSM)

Образец: `app/handlers/examples/survey.py`.

1. `StatesGroup` в `app/states/<name>.py`, экспорт в `app/states/__init__.py`.
2. Первый хендлер: `await state.set_state(...)`. Каждый шаг: `StateFilter(States.step)`,
   валидация, `state.update_data(...)`, следующий `set_state`.
3. Обязательно: хендлер `/cancel` с `StateFilter(States)` — **объявлен раньше** хендлеров шагов,
   иначе текст «/cancel» будет принят как ответ на шаг.
4. Финал: `await state.clear()`. Данные — `await state.get_data()`.
5. Тест проверяет переходы через `harness.state_of(user)`.

### 4.3 Inline-кнопки и callback

Образец: `app/handlers/examples/pagination.py`.

- Для callback с параметрами используй `CallbackData` фабрику (`class X(CallbackData, prefix="x")`),
  фильтр `X.filter()`, аргумент хендлера `callback_data: X`. Не парси строки руками.
- Для простых кнопок — `F.data == "menu:settings"`. Префикс через двоеточие, единый на весь бот.
- Всегда `await callback.answer()` в конце, иначе у пользователя «крутится» кнопка.
- Редактируй сообщение (`edit_text`) вместо отправки нового, если это навигация.

### 4.4 Новая таблица в БД

**Правило:** новая таблица → модель в `app/database/models.py` (создастся автоматически через `create_all`
при старте). Изменение существующей таблицы (колонка, индекс, тип) → миграция. Не делай и то и другое для одного изменения.

1. Класс модели в `models.py` (образец: `User`). `BigInteger` для Telegram ID.
2. Методы доступа в `app/database/database.py` внутри `Database` (образец: `add_user`, `get_user`).
   Всегда `async with self.session_maker() as session`.
3. Те же методы — в `FakeDb` (`tests/conftest.py`).
4. Тест хендлера, который эти методы использует.

### 4.5 Изменение существующей таблицы (миграция)

Образец: `docs/examples/migration_add_columns_example.py`.

1. `just create-migration add_phone_to_users "Добавить телефон"` → файл в `app/database/migrations/versions/`.
2. `check_can_apply` — проверка через `information_schema`, `upgrade` — SQL с `IF NOT EXISTS`, `downgrade` — откат.
3. Обнови модель в `models.py`, чтобы ORM знал о колонке.
4. Миграции применяются при старте; вручную: `just db-migrate`, статус: `just db-migration-status`.

### 4.6 Сервис (логика без aiogram)

Образец: `app/services/broadcast.py`. Класс с зависимостями через `__init__` (`bot`, `db`),
экспорт в `app/services/__init__.py`. Тестируется без харнеса, обычным pytest.

### 4.7 Middleware

Образец: `app/middlewares/user.py`. Регистрация в `app/middlewares/__init__.py`:
`outer_middleware` — на каждый апдейт; `middleware` — только если хендлер совпал.

### 4.8 Кнопка в админке

1. Кнопка в `app/keyboards/admin.py` (`AdminKeyboards.main_admin_menu`), `callback_data="admin_<action>"`.
2. Хендлер в `app/handlers/admin/admin.py` с фильтром `IsAdmin()` в декораторе. Если нужно ответить
   «нет прав» вместо тихого игнорирования — прими аргумент `is_admin: bool` и проверь его в теле.
3. Тест с фикстурой `admin` (ID 777 в тестах задаётся через `ADMIN_USER_IDS` в `tests/conftest.py`).

### 4.9 Нативный выбор пользователя или чата (request_users / request_chat)

Образец: `app/handlers/admin/admins.py` + `AdminKeyboards.pick_user_keyboard`.

- Открыть системный список контактов может только reply-кнопка `KeyboardButton(request_users=...)`,
  inline-кнопки этого не умеют. Поэтому: inline-меню → reply-клавиатура с одной кнопкой выбора и «Отмена».
- Ответ приходит как `message.users_shared` (`F.users_shared`), внутри `users[].user_id`,
  а `first_name/username` — только если запросили `request_name=True` / `request_username=True`.
- Держи выбор в FSM-состоянии и убирай клавиатуру `ReplyKeyboardRemove()` на **каждом** выходе из него:
  успех, кнопка «Отмена», `/cancel` и любое другое сообщение (fallback-хендлер `StateFilter(...)` без
  прочих условий, объявленный последним). Иначе reply-клавиатура останется висеть в чате навсегда.
  Общее правило шаблона: reply-клавиатура живёт только внутри состояния и умирает вместе с ним.
- Для выбора группы/канала аналогично `KeyboardButtonRequestChat` и `F.chat_shared`.

### 4.10 Внешний HTTP API

`aiohttp` уже в зависимостях (через aiogram). Клиент — в `app/services/`, ключ API — в `.env` через
новое поле в `app/config.py` (`Field("", alias="MY_API_KEY")`), в `.env.example` — пустое значение.
Ключ пользователь кладёт сам: скажи ему открыть `.env` в редакторе или используй `just set-token`
как образец для своего скрипта. **Не проси ключ в чат.**

### 4.11 Планировщик / фоновые задачи

Образец: `LivenessService.run_scheduler` в `app/services/liveness.py` — задача создаётся в `on_startup`
(`app/main.py`), отменяется в `on_shutdown`, тикает раз в час и сама решает, пора ли работать.
Запускай через `asyncio.create_task` в `on_startup` или добавь `apscheduler` в `requirements.txt`.
Не блокируй event loop.

### 4.12 Статус пользователя: живой, отключён, заблокировал бота

У пользователя два независимых флага в `users`:

- `is_active` — учётная активность (сбрасывать в `False` можно, например, при бане админом);
- `bot_blocked` — пользователь заблокировал бота или удалил аккаунт. Ставится тремя путями:
  `my_chat_member` (`app/handlers/chat_member.py`, мгновенно), 403 при рассылке (`BroadcastService`),
  прогон проверки живых (`LivenessService`, кнопка «🩺 Проверить живых» в `/admin` и ночной автопрогон
  раз в `LIVENESS_CHECK_INTERVAL_DAYS` дней). Снимается, когда пользователь снова пишет боту.

**Живой** = `is_active AND NOT bot_blocked` — `db.get_alive_users()` / `get_alive_users_count()`.
Рассылки и счётчики в админке считают только живых. Новые выборки «кому отправить» строй на них,
а не на `get_active_users()`.

Сервисные UPDATE по `users` (пометка блокировки, результаты прогона) передают `updated_at=User.updated_at`,
чтобы не подделывать «последнюю активность» пользователя. Делай так же в своих служебных обновлениях.

## 5. Чего не делать

- Не читать и не выводить `.env`, `.env.prod`, `logs/` целиком в чат. Токен — только маскированно.
- Не хранить состояние в глобальных переменных: есть FSM (Redis) и БД.
- Не вызывать `db.*` в `keyboards/` или `states/`. Данные — в хендлерах и сервисах.
- Не отправлять сообщения в цикле без задержек: Telegram ограничивает ~30 сообщений/сек (см. `BroadcastService`).
- Не слать рассылки по `get_active_users()` / всем подряд: заблокировавшие бота дают 403 и тратят лимит. Только `get_alive_users()`.
- Не редактировать одно сообщение прогресса на каждом шаге долгого цикла: Telegram включает flood control на `editMessageText`, экран замирает, а финальный отчёт не доходит. Используй `ProgressReporter` из `app/services/broadcast.py` (троттлинг + устойчивый финал).
- Не менять `check_can_apply` уже применённых миграций.
- Не отключать `IsAdmin()` и проверки прав «для отладки».
- Не коммитить, пока `just check` красный.

## 6. Деплой на сервер

Человек не заходит на сервер руками и не вставляет в чат ни IP, ни пароль, ни ключ. Всё делают команды.

```bash
just rent-server            # 1. если сервера нет: список провайдеров (--json для агента)
just rent-server vdska      #    открыть выбранного провайдера в браузере (партнёрская ссылка автора шаблона)
just venv                   # 2. один раз: в .venv ставится paramiko для SSH
just set-server             # 3. ← человек вставляет IP и пароль на странице в браузере; агент видит только root@123.45.•.•
just deploy                 # 4. Docker на сервере, загрузка проекта и .env.prod, docker compose up, health
just server-logs 30         # 5. проверить, что бот стартовал
just deploy-github          # 6. (опционально) секреты в GitHub через gh CLI → дальше деплой при каждом push в main
```

Сценарий диалога:

1. Спроси: «Есть ли у вас сервер (VPS с Ubuntu)?» Если нет — покажи вывод `just rent-server` и спроси, какой
   провайдер выбрать; по умолчанию предлагай первый в списке. Запусти `just rent-server <slug>` — откроется
   страница регистрации. Скажи: «Создайте сервер с Ubuntu 22.04 или новее, минимальный тариф. Провайдер пришлёт
   IP-адрес и пароль root — они понадобятся на следующем шаге».
2. Перед `just set-server` скажи дословно (без слова «env» и «SSH-ключ»):

   > Сейчас откроется страница с полями «адрес», «пользователь» и «пароль». Вставьте туда IP-адрес и пароль
   > из письма провайдера и нажмите «Подключить». В чат ничего вставлять не нужно. Пароль нигде не сохраняется:
   > скрипт один раз войдёт по нему и переключит сервер на свой ключ.

3. `just deploy` печатает ход работы. Успех — строка `✅ Бот задеплоен`. Затем `just server-logs 30`:
   ищи `Bot @имя started successfully`. Попроси человека отправить боту `/start`.
4. Если человек хочет автодеплой по push: проверь `gh auth status`; если не авторизован — попроси выполнить
   в терминале `gh auth login` (откроется браузер). Затем `just deploy-github`. Значения секретов не печатай.

Что где лежит: `.deploy/server.json` — адрес, порт, пользователь, путь к проекту (без секретов);
`.deploy/deploy_key` — приватный ключ (никогда не читай и не печатай); `.env.prod` — настройки бота на сервере,
создаётся `just init` + `just set-token`. `just doctor` показывает строку «Сервер» с адресом под маской.

Прямой деплой и GitHub Actions используют один скрипт `scripts/remote_deploy.py`; на сервере он запускает
`scripts/deploy.py --ci`. Ручная настройка сервера для тех, кто хочет понимать, что внутри: `docs/SERVER_SETUP.md`.

## 7. Если что-то не так

| Симптом | Куда смотреть |
|---|---|
| Бот не отвечает | `just doctor`, затем `just logs-json 50`: ищи `ERROR` |
| `Router is already attached` в тестах | используй фикстуру `harness`, не создавай `Dispatcher` сам |
| Хендлер не срабатывает | порядок роутеров в `app/handlers/__init__.py`; фильтры состояния |
| `/cancel` не работает в FSM | объяви его раньше хендлеров шагов (см. 4.2) |
| Миграция не применилась | `check_can_apply` вернул False; `just db-migration-status` |
| Токен утёк в чат | скажи человеку сделать `/revoke` в @BotFather, затем `just set-token` |
| Пароль сервера утёк в чат | попроси сменить пароль в панели провайдера; ключ из `.deploy/` при этом продолжает работать |
| `just deploy`: «Нет библиотеки paramiko» | `just venv`, затем повторить |
| `just deploy`: «Сервер не принял пароль или ключ» | `just set-server` заново (ключ на сервере мог быть удалён при переустановке ОС) |
| `just deploy-github`: «gh не авторизован» | человек выполняет `gh auth login` в терминале сам |
