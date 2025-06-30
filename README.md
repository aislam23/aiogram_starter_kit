# 🤖 Aiogram Starter Kit

Профессиональный стартовый шаблон для создания Telegram ботов на **Aiogram v3.20.0** с Docker контейнеризацией.

## ✨ Особенности

- 🐳 **Docker** - полная контейнеризация для разработки и продакшена
- 🚀 **Aiogram v3.20.0** - последняя версия фреймворка
- 🗄️ **PostgreSQL** - надежная база данных
- 📦 **Redis** - быстрое хранилище состояний
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

**Рекомендуется (автоматически через `make init-project`):**
- [ ] Уникальное название проекта
- [ ] Безопасные пароли для БД
- [ ] Свободные порты (если стандартные заняты)
- [ ] Новый Git репозиторий

**Результат:**
- [ ] Бот отвечает на `/start`, `/help`, `/status`
- [ ] Логи показывают успешный запуск
- [ ] Доступ к pgAdmin (опционально)

### 🔧 Ручная настройка (если нужен контроль)

```bash
# Клонируем и настраиваем вручную
git clone git@github.com:aislam23/aiogram_starter_kit.git my_bot
cd my_bot
rm -rf .git && git init  # Очищаем Git историю

# Настраиваем окружение
make setup
nano .env  # Добавляем BOT_TOKEN и BOT_USERNAME

# Запускаем
make dev-d
```

## 📁 Структура проекта

```
aiogram_starter_kit/
├── app/                          # Код приложения
│   ├── handlers/                 # Обработчики команд
│   │   ├── start.py             # Команда /start
│   │   └── help.py              # Команды /help, /status
│   ├── middlewares/             # Промежуточное ПО
│   │   └── logging.py           # Логирование запросов
│   ├── database/                # Работа с БД
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

## 🎬 Интерактивная настройка

Команда `make init-project` запускает мастер, который собирает:

### 📋 Информацию о проекте:
- **🤖 Токен бота** (от @BotFather) - обязательно
- **📛 Username бота** (без @) - обязательно
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

### 📺 Пример работы:

```
╔══════════════════════════════════════════════════════════════╗
║              🚀 AIOGRAM STARTER KIT SETUP 🚀                ║
║          Интерактивная настройка нового проекта              ║
╚══════════════════════════════════════════════════════════════╝

🤖 НАСТРОЙКА БОТА
Введите токен вашего бота: 123456789:ABCdef...
Введите username бота: my_awesome_bot

📁 НАСТРОЙКА ПРОЕКТА  
Название проекта: my_telegram_bot
Имя автора: John Doe
Описание проекта: Бот для управления задачами

🔐 НАСТРОЙКА БЕЗОПАСНОСТИ
Пароль для PostgreSQL: MySecretPass123
Имя базы данных: taskbot_db

🌐 НАСТРОЙКА ПОРТОВ
Порт PostgreSQL: 5433
Порт pgAdmin: 8081

🔧 Начинаем настройку проекта...
📝 Создание .env файла...
🐳 Обновление Docker Compose...
✅ Volumes переименованы в: my_telegram_bot_*
✅ Контейнеры переименованы в: my_awesome_bot_*
📦 Обновление метаданных проекта...
📖 Обновление README.md...
📋 Инициализация Git репозитория...
🧹 Очистка macOS артефактов...

✅ Настройка завершена успешно!

📋 Следующие шаги:
1. make dev-d     # Запустить бота
2. make logs-bot  # Посмотреть логи
3. Протестировать команды: /start, /help, /status
```

## 🏗️ Docker Архитектура

### Многоэтапная сборка

Dockerfile использует многоэтапную сборку для оптимизации:

1. **base** - базовый образ с Python и зависимостями
2. **development** - для разработки (копирует весь код)
3. **production** - для продакшена (только необходимые файлы)

### Сети и volumes

- **bot_network** - изолированная сеть для всех сервисов
- **redis_data** - персистентные данные Redis
- **postgres_data** - персистентные данные PostgreSQL

### Именование контейнеров

Интерактивная настройка автоматически переименовывает контейнеры:

- **Volumes**: `project_name_redis_data`, `project_name_postgres_data`
- **Контейнеры**: `bot_username_bot_dev`, `bot_username_redis_dev`, `bot_username_postgres_dev`

Например, для бота `@my_awesome_bot`:
- `my_awesome_bot_bot_dev` - основной контейнер бота
- `my_awesome_bot_redis_dev` - Redis для разработки  
- `my_awesome_bot_postgres_dev` - PostgreSQL для разработки

## 🔒 Безопасность

- Запуск от непривилегированного пользователя (UID 1000)
- Изолированная Docker сеть
- Переменные окружения для секретов
- Health checks для мониторинга

## 🚀 Деплой в продакшен

### 1. Подготовка

```bash
# Создать .env.prod с продакшен настройками
cp .env.example .env.prod
nano .env.prod
```

### 2. Сборка и запуск

```bash
# Собрать и запустить продакшен образы
make build-prod
make prod
```

### 3. Быстрый деплой

```bash
# Используйте готовый скрипт
./scripts/deploy.sh
```

## 🍎 Работа с macOS

### Очистка системных файлов

macOS создает служебные файлы (.DS_Store, ._*, и др.), которые автоматически исключаются:

```bash
# Очистить macOS артефакты из проекта
make clean-macos

# Настроить глобальный .gitignore для всех проектов
make setup-git-macos
```

### Автоматическое игнорирование

Проект уже настроен для игнорирования macOS файлов:
- **.gitignore** - исключает из Git репозитория
- **.dockerignore** - исключает из Docker образов

## 🐛 Устранение неполадок

### Частые ошибки и решения

#### `ModuleNotFoundError: No module named 'redis'`
```bash
# Пересоберите образ - в requirements.txt уже правильная зависимость
make build
```

#### `AuthenticationError: AUTH <password> called without password`
```bash
# В .env файле оставьте REDIS_PASSWORD пустым
REDIS_PASSWORD=
```

#### `Port already in use`
```bash
# Используйте интерактивную настройку для автоматического изменения портов
make init-project
```

#### Проблемы с токеном бота
```bash
# Проверьте правильность токена
grep BOT_TOKEN .env
# Убедитесь, что бот создан через @BotFather
```

### Команды диагностики

```bash
# Проверка статуса
make status
make health

# Просмотр логов
make logs-bot

# Подключение к контейнерам
make shell      # Bash в боте
make db-shell   # PostgreSQL
make redis-shell # Redis

# Полная переустановка
make clean-all
make dev
```

## 📝 Разработка

### Добавление новых обработчиков

1. Создайте файл в `app/handlers/`
2. Зарегистрируйте роутер в `app/handlers/__init__.py`
3. Перезапустите бота: `make restart-bot`

### Добавление middleware

1. Создайте файл в `app/middlewares/`
2. Зарегистрируйте middleware в `app/middlewares/__init__.py`
3. Перезапустите бота: `make restart-bot`

### Live Reload

В режиме разработки код автоматически обновляется в контейнере при изменении файлов.

### Добавление новых зависимостей

1. Добавьте пакет в `requirements.txt`
2. Пересоберите образ: `make build`
3. Перезапустите: `make restart`

## 📊 Мониторинг

### Логи

Все логи настроены с цветным выводом и структурированием:

```bash
# Просмотр логов в реальном времени
make logs-bot

# Логи определенного сервиса
make logs-db
make logs-redis
```

### Health Checks

Контейнеры имеют встроенные health checks для мониторинга состояния.

## 🎯 Что дальше

После настройки шаблона вы можете:

1. **Добавить новые команды** в `app/handlers/`
2. **Настроить FSM состояния** для сложных диалогов
3. **Интегрировать внешние API** через переменные окружения
4. **Добавить клавиатуры** inline и reply
5. **Настроить админ-панель** для управления ботом
6. **Добавить middleware** для аутентификации
7. **Интегрировать аналитику** и метрики
8. **Настроить CI/CD** для автоматического деплоя

## 📚 Полезные ссылки

- [Документация Aiogram](https://docs.aiogram.dev/)
- [Docker Compose](https://docs.docker.com/compose/)
- [PostgreSQL](https://www.postgresql.org/docs/)
- [Redis](https://redis.io/documentation)

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

*Версия: 1.0.0 | Aiogram: v3.20.0 | Дата: 30.06.2025*
