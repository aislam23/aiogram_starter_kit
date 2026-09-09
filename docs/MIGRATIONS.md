# 🔄 Система миграций базы данных

## Обзор

> **Правило для агентов и людей.** Новая таблица → модель в `app/database/models.py`, она создастся
> автоматически через `create_all` при старте. Изменение существующей таблицы (колонка, индекс, тип)
> → миграция. Не делайте и то и другое для одного изменения. Образец миграции:
> `docs/examples/migration_add_columns_example.py`.

Проект включает полноценную систему автоматических миграций базы данных, которая:

- ✅ **Автоматически применяется** при запуске бота
- 🔍 **Проверяет наличие столбцов** перед применением изменений
- 📝 **Ведет историю** всех примененных миграций
- 🔄 **Поддерживает откат** миграций (опционально)
- 🛡️ **Безопасна** - не ломает существующие данные

## Структура

```
app/database/migrations/
├── __init__.py              # Экспорт основных классов
├── base.py                  # Базовый класс Migration
├── manager.py               # MigrationManager для управления
└── versions/                # Директория с файлами миграций
    ├── __init__.py
    ├── 20241201_000001_initial_tables.py      # Начальные таблицы
    ├── 20241201_000002_add_user_columns_example.py  # Пример
    └── 20241201_000003_add_extra_tables.py   # Дополнительные таблицы
```

## Как это работает

1. **При запуске бота** автоматически вызывается `db.run_migrations()`
2. **MigrationManager** сканирует директорию `versions/` и находит все миграции
3. **Проверяется история** - какие миграции уже применены (таблица `migration_history`)
4. **Применяются новые миграции** в порядке их версий
5. **Записывается результат** в историю миграций

## Создание новой миграции

### Способ 1: Через Makefile (рекомендуется)

```bash
make create-migration NAME=add_user_email DESC="Add email column to users table"
```

### Способ 2: Через скрипт

```bash
python scripts/create_migration.py add_user_email "Add email column to users table"
```

### Способ 3: Вручную

Создайте файл в `app/database/migrations/versions/` с именем формата `YYYYMMDD_HHMMSS_name.py`:

```python
"""
Описание миграции
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class YourMigration(Migration):
    """Детальное описание миграции"""
    
    def get_version(self) -> str:
        return "20241201_120000"  # YYYYMMDD_HHMMSS
    
    def get_description(self) -> str:
        return "Краткое описание изменений"
    
    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        """Проверка, нужно ли применять миграцию"""
        # Проверяем существование столбца/таблицы
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
                AND column_name = 'email'
            );
        """))
        return not result.scalar()  # Применяем если столбца нет
    
    async def upgrade(self, connection: AsyncConnection) -> None:
        """Применение миграции"""
        await connection.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS email VARCHAR(255);
        """))
        
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """))
        
        logger.info("✅ Added email column to users table")
    
    async def downgrade(self, connection: AsyncConnection) -> None:
        """Откат миграции (опционально)"""
        await connection.execute(text("""
            DROP INDEX IF EXISTS idx_users_email;
        """))
        await connection.execute(text("""
            ALTER TABLE users DROP COLUMN IF EXISTS email;
        """))
        logger.info("✅ Removed email column from users table")
```

## Управление миграциями

### Просмотр статуса

```bash
# Показать примененные миграции
make db-migration-status

# Вывод:
# 20241201_000001 - InitialTablesMigration (2025-07-07 08:09:21)
# 20241201_000003 - AddExtraTablesMigration (2025-07-07 08:09:21)
```

### Применение вручную

```bash
# Применить все неприменённые миграции
make db-migrate
```

### Проверка структуры БД

```bash
# Посмотреть структуру таблицы
docker exec aiogram_postgres_dev psql -U botuser botdb -c "\d users"

# Список всех таблиц
docker exec aiogram_postgres_dev psql -U botuser botdb -c "\dt"
```

## Лучшие практики

### 1. Всегда проверяйте перед изменением

```python
async def check_can_apply(self, connection: AsyncConnection) -> bool:
    # Проверяем, что изменение еще не применено
    result = await connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'new_column'
        );
    """))
    return not result.scalar()
```

### 2. Используйте IF NOT EXISTS

```python
# ✅ Хорошо
await connection.execute(text("""
    ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
"""))

# ❌ Плохо - вызовет ошибку если столбец существует
await connection.execute(text("""
    ALTER TABLE users ADD COLUMN email VARCHAR(255);
"""))
```

### 3. Логируйте действия

```python
async def upgrade(self, connection: AsyncConnection) -> None:
    logger.info("Adding email column to users table...")
    # ... выполнение SQL
    logger.info("✅ Successfully added email column")
```

### 4. Делайте миграции атомарными

Каждая миграция должна выполнять одно логическое изменение:

- ✅ `add_user_email` - добавляет email
- ✅ `create_payments_table` - создает таблицу платежей
- ❌ `update_database` - слишком общее название

### 5. Версионирование

Используйте формат `YYYYMMDD_HHMMSS` для версий:
- Автоматическая сортировка по дате
- Избежание конфликтов при параллельной разработке
- Понятная хронология изменений

## Примеры миграций

### Добавление столбца

```python
async def upgrade(self, connection: AsyncConnection) -> None:
    await connection.execute(text("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS subscription_ends_at TIMESTAMP WITH TIME ZONE;
    """))
```

### Создание таблицы

```python
async def upgrade(self, connection: AsyncConnection) -> None:
    await connection.execute(text("""
        CREATE TABLE IF NOT EXISTS payments (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            amount DECIMAL(10, 2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'RUB',
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """))
    
    # Создаем индексы
    await connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
    """))
```

### Изменение типа столбца

```python
async def upgrade(self, connection: AsyncConnection) -> None:
    # Изменяем тип с VARCHAR на TEXT
    await connection.execute(text("""
        ALTER TABLE messages 
        ALTER COLUMN content TYPE TEXT;
    """))
```

### Добавление ограничения

```python
async def upgrade(self, connection: AsyncConnection) -> None:
    await connection.execute(text("""
        ALTER TABLE users 
        ADD CONSTRAINT check_phone_format 
        CHECK (phone ~ '^\+?[0-9]{10,15}$');
    """))
```

## Отладка проблем

### Миграция не применяется

1. Проверьте метод `check_can_apply()` - возвращает ли он `True`
2. Посмотрите логи: `docker logs aiogram_bot_dev`
3. Проверьте таблицу истории: 
   ```sql
   SELECT * FROM migration_history;
   ```

### Ошибка при применении

1. Проверьте SQL синтаксис
2. Убедитесь, что используете `IF NOT EXISTS`
3. Проверьте зависимости (внешние ключи, индексы)

### Конфликт версий

Если два разработчика создали миграции с одинаковой версией:
1. Переименуйте один из файлов с новым timestamp
2. Обновите метод `get_version()` в классе

## Интеграция с CI/CD

### GitHub Actions

```yaml
- name: Run migrations
  run: |
    docker-compose run --rm bot python -c "
    import asyncio
    from app.database import db
    asyncio.run(db.run_migrations())
    "
```

### Pre-commit hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Проверяем, что все миграции имеют уникальные версии
python scripts/check_migration_versions.py
```

## FAQ

**Q: Можно ли откатить миграцию?**
A: Да, если реализован метод `downgrade()`. Но это нужно делать вручную и осторожно.

**Q: Что если миграция упала посередине?**
A: Миграции выполняются в транзакции. При ошибке все изменения откатываются.

**Q: Как пропустить миграцию?**
A: Добавьте запись в `migration_history` вручную или измените `check_can_apply()`.

**Q: Можно ли изменить уже примененную миграцию?**
A: Нет! Создайте новую миграцию с нужными изменениями.

**Q: Как удалить столбец безопасно?**
A: Сначала уберите его использование в коде, затем создайте миграцию для удаления. 