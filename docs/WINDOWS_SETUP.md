# Настройка проекта на Windows

Aiogram Starter Kit полностью поддерживает Windows благодаря кроссплатформенным инструментам.

## Содержание

1. [Установка необходимых инструментов](#установка-необходимых-инструментов)
2. [Установка Just (рекомендуется)](#установка-just-рекомендуется)
3. [Альтернатива: использование Python-скриптов](#альтернатива-использование-python-скриптов)
4. [Быстрый старт](#быстрый-старт)
5. [Таблица соответствия команд](#таблица-соответствия-команд)

---

## Установка необходимых инструментов

### 1. Docker Desktop

1. Скачайте [Docker Desktop для Windows](https://www.docker.com/products/docker-desktop/)
2. Установите и перезагрузите компьютер
3. Запустите Docker Desktop
4. Проверьте установку:
   ```powershell
   docker --version
   docker compose version
   ```

### 2. Git

1. Скачайте [Git для Windows](https://git-scm.com/download/win)
2. При установке выберите "Use Git from Windows Command Prompt"
3. Проверьте установку:
   ```powershell
   git --version
   ```

### 3. Python (уже должен быть)

Проверьте наличие Python:
```powershell
python --version
```

Если Python не установлен, скачайте с [python.org](https://www.python.org/downloads/).

---

## Установка Just (рекомендуется)

Just — это современный кроссплатформенный task runner, альтернатива Make.

### Способ 1: Winget (Windows 10/11)

```powershell
winget install Casey.Just
```

### Способ 2: Scoop

```powershell
# Установка Scoop (если не установлен)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression

# Установка Just
scoop install just
```

### Способ 3: Chocolatey

```powershell
choco install just
```

### Проверка установки

```powershell
just --version
```

---

## Альтернатива: использование Python-скриптов

Если не хотите устанавливать Just, можно использовать Python-скрипты напрямую:

```powershell
# Инициализация проекта
python scripts/init_project.py

# Деплой в продакшен
python scripts/deploy.py
```

Для Docker-команд используйте docker-compose напрямую:

```powershell
# Запуск в dev-режиме
docker-compose up --build -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

---

## Быстрый старт

### 1. Клонирование репозитория

```powershell
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### 2. Инициализация проекта

```powershell
# С Just
just init-project

# Или с Python
python scripts/init_project.py
```

### 3. Запуск бота

```powershell
# С Just
just dev-d

# Или напрямую
docker-compose up --build -d
```

### 4. Просмотр логов

```powershell
# С Just
just logs-bot

# Или напрямую
docker-compose logs -f bot
```

### 5. Остановка

```powershell
# С Just
just stop

# Или напрямую
docker-compose down
```

---

## Таблица соответствия команд

| Make (macOS/Linux) | Just (кроссплатформ.) | Docker Compose (напрямую) |
|--------------------|----------------------|---------------------------|
| `make dev` | `just dev` | `docker-compose up --build` |
| `make dev-d` | `just dev-d` | `docker-compose up --build -d` |
| `make stop` | `just stop` | `docker-compose down` |
| `make logs-bot` | `just logs-bot` | `docker-compose logs -f bot` |
| `make status` | `just status` | `docker-compose ps` |
| `make shell` | `just shell` | `docker-compose exec bot bash` |
| `make db-shell` | `just db-shell` | `docker-compose exec postgres psql -U botuser -d botdb` |
| `make test` | `just test` | `docker-compose exec bot python -m pytest tests/ -v` |
| `make prod` | `just prod` | `docker-compose -f docker-compose.prod.yml up --build -d` |
| `make init-project` | `just init-project` | `python scripts/init_project.py` |
| `make restart-bot` | `just restart-bot` | `docker-compose restart bot` |

---

## Решение проблем

### "just" не распознается как команда

Перезапустите терминал после установки Just, или добавьте путь в переменную PATH.

### Docker commands fail

1. Убедитесь, что Docker Desktop запущен
2. Проверьте, что WSL 2 установлен (требуется для Docker Desktop)
3. Попробуйте перезапустить Docker Desktop

### ANSI-коды (цвета) отображаются как символы

В PowerShell выполните:
```powershell
$env:TERM = "xterm-256color"
```

Или используйте Windows Terminal вместо стандартной командной строки.

### Путь содержит кириллицу или пробелы

Избегайте путей с пробелами и кириллицей:
- ❌ `C:\Users\Иван Иванов\Мои проекты\bot`
- ✅ `C:\projects\bot`

---

## Рекомендуемые инструменты для Windows

- **Windows Terminal** — современный терминал с поддержкой вкладок
- **VS Code** — редактор с отличной поддержкой Docker и Python
- **Git Bash** — Unix-подобный терминал (устанавливается вместе с Git)

---

## Дополнительно: WSL (Windows Subsystem for Linux)

Если хотите полную совместимость с Linux-командами, можно установить WSL:

```powershell
# В PowerShell от администратора
wsl --install
```

После установки WSL вы сможете использовать все команды make и bash-скрипты напрямую.
