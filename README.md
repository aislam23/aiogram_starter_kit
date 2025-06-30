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
- 🔒 **Безопасность** - запуск от непривилегированного пользователя

## 📁 Структура проекта

```
aiogram_starter_kit/
├── app/                          # Код приложения
│   ├── handlers/                 # Обработчики команд
│   │   ├── __init__.py
│   │   ├── start.py             # Команда /start
│   │   └── help.py              # Команды /help, /status
│   ├── middlewares/             # Промежуточное ПО
│   │   ├── __init__.py
│   │   └── logging.py           # Логирование запросов
│   ├── database/                # Работа с БД
│   │   └── __init__.py
│   ├── utils/                   # Утилиты
│   │   └── __init__.py
│   ├── __init__.py
│   ├── main.py                  # Главный файл бота
│   └── config.py                # Конфигурация
├── scripts/                     # Скрипты
│   └── init.sql                 # Инициализация БД
├── docker-compose.yml           # Разработка
├── docker-compose.prod.yml      # Продакшен
├── Dockerfile                   # Многоэтапная сборка
├── Makefile                     # Команды управления
├── requirements.txt             # Python зависимости
├── .env.example                 # Пример переменных окружения
├── .dockerignore               # Исключения для Docker
└── README.md                   # Этот файл
```

## 🍎 Работа с macOS

### Очистка системных файлов

macOS создает служебные файлы (.DS_Store, ._*, и др.), которые не должны попадать в репозиторий:

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
- **Глобальный .gitignore** - исключает из всех ваших Git проектов

## 🚀 Быстрый старт

### 1. Настройка окружения

```bash
# Создать .env файл
make setup

# (Опционально) Настроить Git для macOS
make setup-git-macos

# Отредактировать .env файл - добавить токен бота
nano .env
```

### 2. Запуск разработки

```bash
# Запуск в фоновом режиме
make dev-d

# Запуск с pgAdmin (доступен на http://localhost:8080)
make dev-tools

# Просмотр логов
make logs-bot
```

### 3. Проверка работы

```bash
# Статус сервисов
make status

# Проверка здоровья
make health
```

## 🔧 Команды управления

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

## 🗄️ База данных

### Подключение к PostgreSQL

- **Host**: localhost
- **Port**: 5432
- **Database**: botdb
- **User**: botuser
- **Password**: securepassword (измените в .env)

### pgAdmin (при использовании make dev-tools)

- **URL**: http://localhost:8080
- **Email**: admin@admin.com
- **Password**: admin

## 📦 Redis

### Подключение к Redis

- **Host**: localhost
- **Port**: 6379
- **Database**: 0

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

# Environment
ENV=development

# Logging
LOG_LEVEL=INFO
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

## 🔒 Безопасность

- Запуск от непривилегированного пользователя (UID 1000)
- Изолированная Docker сеть
- Переменные окружения для секретов
- Health checks для мониторинга

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

## 🚀 Деплой в продакшен

### 1. Подготовка

```bash
# Создать .env.prod с продакшен настройками
cp .env.example .env.prod
nano .env.prod
```

### 2. Сборка

```bash
# Собрать продакшен образы
make build-prod
```

### 3. Запуск

```bash
# Запустить в продакшене
make prod
```

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

## 🛠️ Расширение функциональности

### Добавление новых зависимостей

1. Добавьте пакет в `requirements.txt`
2. Пересоберите образ: `make build`
3. Перезапустите: `make restart`

### Интеграция с внешними API

Добавьте конфигурацию в `app/config.py` и используйте переменные окружения.

## 🐛 Отладка

### Подключение к контейнерам

```bash
# Bash в контейнере бота
make shell

# PostgreSQL консоль
make db-shell

# Redis консоль
make redis-shell
```

### Просмотр статуса

```bash
# Статус всех сервисов
make status

# Проверка здоровья
make health
```

## 📚 Полезные ссылки

- [Документация Aiogram](https://docs.aiogram.dev/)
- [Docker Compose](https://docs.docker.com/compose/)
- [PostgreSQL](https://www.postgresql.org/docs/)
- [Redis](https://redis.io/documentation)
- [Устранение неполадок](./TROUBLESHOOTING.md) 🔧

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
