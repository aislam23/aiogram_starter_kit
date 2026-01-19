# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Aiogram Starter Kit - a Telegram bot template built on Aiogram v3.20.0 with Docker, PostgreSQL, Redis, and an admin panel with broadcast functionality.

## Common Commands

### Development
```bash
make dev           # Start with live logs
make dev-d         # Start in background
make stop          # Stop all services
make restart-bot   # Restart only the bot container
make logs-bot      # View bot logs
```

### Database
```bash
make db-shell                    # PostgreSQL console
make db-migrate                  # Run pending migrations
make db-migration-status         # Show applied migrations
make create-migration NAME=name DESC="description"  # Create new migration
```

### Testing & Debugging
```bash
make test          # Run pytest in container
make shell         # Bash inside bot container
make status        # Show container status
```

### Production
```bash
make prod          # Start production (validates .env.prod first)
make prod-stop     # Stop production
```

### Local Bot API (файлы до 2GB)
```bash
make dev-local     # Start with Local Bot API Server
make api-status    # Check Local API status
make api-logs      # View Local API logs
make stop-local    # Stop Local API environment
```

## Architecture

### Entry Point Flow
`app/main.py` → creates Bot + Dispatcher → registers middlewares via `setup_middlewares(dp)` → registers routers via `setup_routers(dp)` → on startup calls `db.create_tables()` which runs migrations → starts polling.

### Key Singletons
- `settings` (app/config.py) - Pydantic Settings loaded from `.env`
- `db` (app/database/__init__.py) - Database class with session_maker and migration_manager

### Handler Pattern (Aiogram v3)
Handlers use routers. Each handler file creates a `router = Router()` and decorates async functions:
```python
from aiogram import Router
from aiogram.filters import CommandStart

router = Router()

@router.message(CommandStart())
async def start_command(message: Message):
    ...
```
Routers are included in dispatcher via `app/handlers/__init__.py:setup_routers()`.

### Middleware Registration
Middlewares are registered per-event type in `app/middlewares/__init__.py`:
```python
dp.message.middleware(LoggingMiddleware())
dp.callback_query.middleware(LoggingMiddleware())
```
`UserMiddleware` auto-saves users to database on every message/callback.

### Database Migrations
Custom migration system in `app/database/migrations/`. Migrations are Python classes inheriting from `Migration` base class:
- `get_version()` - returns `YYYYMMDD_HHMMSS` timestamp
- `check_can_apply()` - returns True if migration should run
- `upgrade()` - applies the migration
- `downgrade()` - optional rollback

Migrations run automatically on bot startup via `db.create_tables()`.

### FSM States
States for multi-step interactions defined in `app/states/`. Used with Redis storage for persistence across restarts.

### Admin Access
Admin user IDs configured in `.env` as `ADMIN_USER_IDS=[123456789]`. Check with `settings.is_admin(user_id)`.

### Local Bot API
Optional support for Local Bot API Server (2GB file uploads instead of 50MB):
- Configuration in `app/config.py`: `use_local_api`, `local_api_url`, `file_upload_limit_mb` properties
- Bot initialization in `app/main.py`: uses `TelegramAPIServer` and `AiohttpSession` when enabled
- Admin UI in `app/handlers/admin/api_settings.py`: status check, mode switching instructions
- Docker service `telegram-bot-api` with profile `local-api` in `docker-compose.yml`

## Language

The codebase uses Russian for comments, docstrings, and user-facing messages.
