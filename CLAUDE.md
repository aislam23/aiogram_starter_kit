# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Aiogram Starter Kit - a Telegram bot template built on Aiogram v3.20.0 with Docker, PostgreSQL, Redis, and an admin panel with broadcast functionality.

## Common Commands

The project supports both `just` (cross-platform) and `make` (macOS/Linux). Use `just` for Windows compatibility.

### Development
```bash
just dev           # Start with live logs
just dev-d         # Start in background
just stop          # Stop all services
just restart-bot   # Restart only the bot container
just logs-bot      # View bot logs
```

### Database
```bash
just db-shell                              # PostgreSQL console
just db-migrate                            # Run pending migrations
just db-migration-status                   # Show applied migrations
just create-migration name "description"   # Create new migration
```

### Testing & Debugging
```bash
just test          # Run pytest in container
just shell         # Bash inside bot container
just status        # Show container status
```

### Production
```bash
just prod          # Start production (validates .env.prod first)
just prod-stop     # Stop production
```

### Local Bot API (файлы до 2GB)
```bash
just dev-local     # Start with Local Bot API Server
just api-status    # Check Local API status
just api-logs      # View Local API logs
just stop-local    # Stop Local API environment
```

### Cross-Platform Scripts
```bash
python scripts/init_project.py  # Interactive project setup
python scripts/deploy.py        # Production deployment
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
