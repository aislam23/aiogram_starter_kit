# 🤖 Aiogram Starter Kit

Профессиональный стартовый шаблон для создания Telegram ботов на **Aiogram v3.20.0** с Docker контейнеризацией.

## ✨ Особенности

- 🐳 **Docker** - полная контейнеризация для разработки и продакшена
- 🚀 **Aiogram v3.20.0** - последняя версия фреймворка
- 🗄️ **PostgreSQL** - надежная база данных с SQLAlchemy
- 📦 **Redis** - быстрое хранилище состояний
- 👨‍💼 **Админская панель** - управление ботом и рассылки
- 📊 **Статистика** - мониторинг пользователей и активности
- 📤 **Система рассылок** - массовая отправка с прогрессом
- 📝 **Логирование** - красивые логи с Loguru
- 🔧 **Pydantic** - валидация конфигурации
- 🛠️ **Makefile** - удобные команды для управления
- 🎯 **Интерактивная настройка** - мастер setup за 2 минуты
- 🔒 **Безопасность** - запуск от непривилегированного пользователя

## 🚀 Быстрый старт

### 🎯 Новый проект за 2 минуты (рекомендуется!)

```bash
# Клонируем шаблон и запускаем интерактивную настройку
git clone git@github.com:aislam23/aiogram_starter_kit.git my_awesome_bot
cd my_awesome_bot
make init-project  # 🚀 Интерактивный мастер настройки
make dev-d         # Запуск готового бота
```

### 🤖 Настройка компьютера с помощью нейронки

Если на вашем компьютере ещё не установлены необходимые программы, скопируйте промпт ниже и отправьте его в ChatGPT, Claude или другую нейронку. Она определит вашу ОС и установит всё, что нужно.

<details>
<summary>📋 Нажмите, чтобы раскрыть промпт</summary>

```text
Мне нужно подготовить компьютер к разработке Telegram-бота на базе шаблона Aiogram Starter Kit.
Определи мою операционную систему и установи всё необходимое.

## Обязательные программы

1. **Git** — система контроля версий. Нужна для клонирования шаблона и работы с репозиторием.
2. **Docker Desktop** (включает Docker Engine и Docker Compose) — все сервисы проекта (бот, PostgreSQL, Redis) запускаются в контейнерах. Без Docker ничего не работает.
3. **Python 3.11+** — нужен для запуска скрипта интерактивной настройки проекта (scripts/init_project.py).

## Рекомендуемые программы

4. **Just** (command runner) — кроссплатформенная альтернатива Make. Удобнее на Windows, где Make не предустановлен. На macOS/Linux можно использовать Make, который уже есть в системе.
5. **GitHub CLI (gh)** — позволяет создать GitHub-репозиторий прямо из терминала во время настройки проекта. Без него репозиторий нужно будет создать вручную на сайте.

## Инструкции по установке

### macOS
- Git: обычно уже установлен. Проверь: `git --version`. Если нет — установится при первом вызове или через `brew install git`.
- Docker Desktop: скачать с https://docs.docker.com/desktop/setup/install/mac-install/ или `brew install --cask docker`. После установки — запустить Docker Desktop и дождаться, пока иконка в трее перестанет анимироваться.
- Python: `brew install python@3.11` или скачать с https://www.python.org/downloads/
- Just: `brew install just`
- GitHub CLI: `brew install gh`

### Windows
- Git: скачать с https://git-scm.com/downloads/win или `winget install Git.Git`
- Docker Desktop: скачать с https://docs.docker.com/desktop/setup/install/windows-install/ или `winget install Docker.DockerDesktop`. После установки — перезагрузить компьютер и запустить Docker Desktop.
- Python: скачать с https://www.python.org/downloads/ (при установке обязательно поставить галочку "Add Python to PATH") или `winget install Python.Python.3.11`
- Just: `winget install Casey.Just`
- GitHub CLI: `winget install GitHub.cli`

### Linux (Ubuntu/Debian)
- Git: `sudo apt update && sudo apt install -y git`
- Docker: установить по официальной инструкции https://docs.docker.com/engine/install/ubuntu/, затем `sudo apt install -y docker-compose-plugin`. Добавить пользователя в группу docker: `sudo usermod -aG docker $USER` и перелогиниться.
- Python: `sudo apt install -y python3 python3-pip`
- Just: `curl -q 'https://proget.makedeb.org/debian-feeds/prebuilt-mpr.pub' | gpg --dearmor | sudo tee /usr/share/keyrings/prebuilt-mpr-archive-keyring.gpg > /dev/null && echo "deb [signed-by=/usr/share/keyrings/prebuilt-mpr-archive-keyring.gpg] https://proget.makedeb.org prebuilt-mpr $(lsb_release -cs)" | sudo tee /etc/apt/sources.list.d/prebuilt-mpr.list && sudo apt update && sudo apt install -y just`
- GitHub CLI: смотри https://github.com/cli/cli/blob/trunk/docs/install_linux.md

## После установки

Проверь, что всё работает, выполнив эти команды в терминале:
```
git --version
docker --version
docker compose version
python3 --version
```

Если все четыре команды вернули версии без ошибок — компьютер готов.

Далее я склонирую и настрою проект:
```
git clone git@github.com:aislam23/aiogram_starter_kit.git my_awesome_bot
cd my_awesome_bot
make init-project
```
```

</details>

**Готово!** 🎉 Интерактивный мастер:
- Соберет информацию о боте (токен, username, описание)
- Настроит все конфигурационные файлы
- Обновит порты при конфликтах
- Инициализирует новый Git репозиторий
- Покажет следующие шаги

### ✅ Быстрый чек-лист

**Обязательно:**
- [ ] BOT_TOKEN от @BotFather
- [ ] BOT_USERNAME вашего бота
- [ ] ADMIN_USER_IDS (ваш Telegram ID для админки)

**Рекомендуется (автоматически через `make init-project`):**
- [ ] Уникальное название проекта
- [ ] Безопасные пароли для БД
- [ ] Свободные порты (если стандартные заняты)
- [ ] Новый Git репозиторий

**Результат:**
- [ ] Бот отвечает на `/start`, `/help`, `/admin`
- [ ] Админская панель работает (команда `/admin`)
- [ ] Логи показывают успешный запуск
- [ ] База данных инициализирована

## 👨‍💼 Админская панель

### Возможности админа

- **📊 Статистика бота**: количество пользователей, статус, время запуска
- **📤 Система рассылок**: отправка сообщений любого типа всем пользователям
- **🔗 Кнопки в рассылках**: добавление inline кнопок с ссылками
- **📈 Прогресс рассылки**: отслеживание процесса отправки в реальном времени
- **📋 Итоговая статистика**: количество доставленных сообщений

### Настройка админов

В файле `.env` укажите ID администраторов:

```env
# Список админов (JSON массив или через запятую)
ADMIN_USER_IDS=[123456789, 987654321]
# или
ADMIN_USER_IDS=123456789,987654321
```

### Как использовать

1. **Команда `/admin`** - открывает админскую панель со статистикой
2. **Кнопка "Рассылка"** - запускает мастер создания рассылки
3. **Отправьте сообщение** любого типа (текст, фото, видео, документ)
4. **Добавьте кнопку** (опционально) в формате: `Текст кнопки | https://example.com`
5. **Подтвердите отправку** - начнется рассылка с показом прогресса
6. **Получите статистику** - количество доставленных сообщений

### Поддерживаемые типы сообщений

- ✅ Текстовые сообщения
- ✅ Фотографии с подписями
- ✅ Видео с подписями
- ✅ Документы с подписями
- ✅ Аудио с подписями
- ✅ Голосовые сообщения
- ✅ Видео-заметки
- ✅ GIF анимации
- ✅ Стикеры

## 📁 Структура проекта

```
aiogram_starter_kit/
├── app/                          # Код приложения
│   ├── handlers/                 # Обработчики команд
│   │   ├── admin/               # Админские хендлеры
│   │   │   ├── __init__.py      # Инициализация
│   │   │   ├── admin.py         # Команда /admin и рассылки
│   │   │   └── api_settings.py  # Настройки Local Bot API
│   │   ├── start.py             # Команда /start
│   │   └── help.py              # Команды /help, /status
│   ├── middlewares/             # Промежуточное ПО
│   │   ├── logging.py           # Логирование запросов
│   │   └── user.py              # Автосохранение пользователей
│   ├── database/                # Работа с БД
│   │   ├── models.py            # SQLAlchemy модели
│   │   ├── database.py          # Класс для работы с БД
│   │   └── __init__.py          # Инициализация
│   ├── keyboards/               # Клавиатуры
│   │   ├── admin.py             # Админские клавиатуры
│   │   └── __init__.py          # Инициализация
│   ├── services/                # Сервисы
│   │   ├── broadcast.py         # Сервис рассылок
│   │   └── __init__.py          # Инициализация
│   ├── states/                  # FSM состояния
│   │   ├── admin.py             # Состояния админки
│   │   └── __init__.py          # Инициализация
│   ├── utils/                   # Утилиты
│   ├── main.py                  # Главный файл бота
│   └── config.py                # Конфигурация
├── scripts/                     # Скрипты
│   ├── init-project.sh          # Интерактивная настройка
│   ├── init.sql                 # Инициализация БД
│   └── clean-macos.sh           # Очистка macOS файлов
├── docker-compose.yml           # Разработка
├── docker-compose.prod.yml      # Продакшен
├── Dockerfile                   # Многоэтапная сборка
├── Makefile                     # Команды управления
├── requirements.txt             # Python зависимости
└── .env.example                 # Пример переменных окружения
```

## 🔧 Команды управления

### Настройка и инициализация
```bash
make init-project        # 🚀 Интерактивная настройка нового проекта (рекомендуется!)
make setup               # Создать .env файл из примера  
make setup-git-macos     # Настроить глобальный .gitignore для macOS
```

### Разработка
```bash
make dev          # Запуск среды разработки
make dev-d        # Запуск в фоновом режиме
make dev-tools    # Запуск с инструментами (pgAdmin)
make stop         # Остановка разработки
```

### Продакшен
```bash
make prod         # Запуск продакшен среды
make prod-stop    # Остановка продакшена
make build-prod   # Сборка продакшен образов
```

### Логи и мониторинг
```bash
make logs         # Все логи
make logs-bot     # Логи бота
make logs-db      # Логи базы данных
make logs-redis   # Логи Redis
```

### Доступ к контейнерам
```bash
make shell        # Bash в контейнере бота
make db-shell     # PostgreSQL консоль
make redis-shell  # Redis консоль
```

### Управление сервисами
```bash
make restart      # Перезапуск всех сервисов
make restart-bot  # Перезапуск только бота
make status       # Статус сервисов
make health       # Проверка здоровья
```

### Очистка
```bash
make clean        # Очистка контейнеров и образов
make clean-all    # Полная очистка включая volumes
make clean-macos  # Очистка macOS артефактов (.DS_Store и др.)
```

## ⚙️ Конфигурация

Все настройки находятся в файле `.env`:

```env
# Bot Configuration
BOT_TOKEN=your_bot_token_here
BOT_USERNAME=your_bot_username

# Admin Configuration
ADMIN_USER_IDS=[123456789, 987654321]

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=botdb
POSTGRES_USER=botuser
POSTGRES_PASSWORD=securepassword

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Environment
ENV=development

# Logging
LOG_LEVEL=INFO
```

## 🗄️ База данных

### Автоматические миграции

Проект включает систему автоматических миграций базы данных:

- **Автоприменение**: Миграции применяются автоматически при запуске бота
- **Проверка столбцов**: Система проверяет наличие нужных столбцов перед применением
- **История миграций**: Ведется журнал примененных миграций
- **Откат**: Поддержка отката миграций (опционально)

📚 **[Подробная документация по миграциям](docs/MIGRATIONS.md)**

### Работа с миграциями

```bash
# Создание новой миграции
make create-migration NAME=add_user_phone DESC="Add phone column to users"

# Применение миграций вручную
make db-migrate

# Просмотр статуса миграций
make db-migration-status

# Создание миграции через скрипт
python scripts/create_migration.py add_user_phone "Add phone column to users"
```

### Структура миграций

```
app/database/migrations/
├── __init__.py              # Экспорт основных классов
├── base.py                  # Базовый класс Migration
├── manager.py               # MigrationManager
└── versions/                # Файлы миграций
    ├── __init__.py
    ├── 20241201_000001_initial_tables.py
    └── 20241201_000002_add_user_columns_example.py
```

### Автоматические таблицы

При запуске бота автоматически создаются таблицы:

- **users** - пользователи бота (ID, username, имя, дата регистрации)
- **bot_stats** - статистика бота (количество пользователей, время запуска)
- **migration_history** - история примененных миграций

### Подключение к PostgreSQL

- **Host**: localhost
- **Port**: 5432 (или заданный в интерактивной настройке)
- **Database**: botdb
- **User**: botuser
- **Password**: securepassword (измените в .env)

### pgAdmin (при использовании make dev-tools)

- **URL**: http://localhost:8080
- **Email**: admin@admin.com
- **Password**: admin

## 🌐 Local Bot API (файлы до 2GB)

По умолчанию Telegram боты ограничены 50MB для загрузки файлов. Local Bot API Server снимает это ограничение.

### Возможности

- 📤 Загрузка файлов до **2000 MB** (вместо 50 MB)
- 📥 Скачивание файлов **без ограничений** (вместо 20 MB)
- 🚀 Работа с файлами напрямую через локальный сервер

### Настройка

1. **Получите credentials** на [my.telegram.org](https://my.telegram.org):
   - Авторизуйтесь с номером телефона
   - Перейдите в "API development tools"
   - Создайте приложение и скопируйте `API_ID` и `API_HASH`

2. **Добавьте в `.env`**:
   ```env
   USE_LOCAL_API=true
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=abcdef1234567890
   ```

3. **Запустите с Local API**:
   ```bash
   make dev-local      # Запуск в фоне
   make dev-local-logs # Запуск с логами
   ```

### Команды управления

```bash
make dev-local      # Запуск с Local Bot API
make api-status     # Проверка статуса сервера
make api-logs       # Просмотр логов
make api-restart    # Перезапуск сервера
make stop-local     # Остановка всех сервисов
```

### Управление через админку

1. Откройте админскую панель: `/admin`
2. Нажмите **"⚙️ Настройки API"**
3. Используйте кнопки для просмотра статуса и инструкций по переключению

### Важные замечания

- ⚠️ Переключение режимов требует перезапуска бота
- 📦 Local API Server требует ~100-200 MB оперативной памяти
- 💾 Файлы хранятся в Docker volume `telegram_bot_api_data`

## 🎬 Интерактивная настройка

Команда `make init-project` запускает мастер, который собирает:

### 📋 Информацию о проекте:
- **🤖 Токен бота** (от @BotFather) - обязательно
- **📛 Username бота** (без @) - обязательно
- **👨‍💼 ID администраторов** (ваш Telegram ID) - обязательно
- **📁 Название проекта** (для Docker volumes)
- **👤 Имя автора**
- **📝 Описание проекта**
- **🔐 Пароли для БД**
- **🌐 Порты** (если стандартные заняты)

### 🔧 И автоматически:
- ✅ Создает правильный `.env` файл
- ✅ Обновляет `docker-compose.yml` с новыми портами
- ✅ Переименовывает Docker volumes под ваш проект
- ✅ Переименовывает контейнеры под имя бота (например: `my_bot_bot_dev`)
- ✅ Обновляет метаданные в `app/__init__.py`
- ✅ Изменяет заголовок в `README.md`
- ✅ Инициализирует новый Git репозиторий
- ✅ Делает первый commit с описанием проекта
- ✅ Очищает macOS артефакты

## 📚 Полезные ссылки

- [Документация Aiogram](https://docs.aiogram.dev/)
- [Docker Compose](https://docs.docker.com/compose/)
- [PostgreSQL](https://www.postgresql.org/docs/)
- [Redis](https://redis.io/documentation)
- [SQLAlchemy](https://docs.sqlalchemy.org/)

## 🤝 Вклад в проект

1. Fork проекта
2. Создайте feature branch
3. Commit изменения
4. Push в branch
5. Создайте Pull Request

## 📄 Лицензия

MIT License - см. файл LICENSE для деталей.

---

**Создан с ❤️ для разработчиков Telegram ботов**

*Версия: 2.0.0 | Aiogram: v3.20.0 | Дата: 30.06.2025*
