"""
Менеджер миграций базы данных
"""
import importlib.util
import time
from pathlib import Path
from typing import List

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .base import Migration


class MigrationManager:
    """Менеджер для управления миграциями базы данных"""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.migrations_dir = Path(__file__).parent / "versions"
        self.migrations_dir.mkdir(exist_ok=True)

    async def ensure_migration_table(self, connection: AsyncConnection) -> None:
        """Создает таблицу миграций если её нет"""
        try:
            # Проверяем существование таблицы
            result = await connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'migration_history'
                );
            """))
            exists = result.scalar()

            if not exists:
                # Создаем таблицу миграций
                await connection.execute(text("""
                    CREATE TABLE migration_history (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(20) UNIQUE NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        execution_time FLOAT
                    );
                """))
                logger.info("✅ Created migration_history table")
        except Exception as e:
            logger.error(f"❌ Error creating migration table: {e}")
            raise

    async def get_applied_migrations(self, connection: AsyncConnection) -> List[str]:
        """Получает список примененных миграций"""
        try:
            result = await connection.execute(text(
                "SELECT version FROM migration_history ORDER BY version"
            ))
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting applied migrations: {e}")
            return []

    def discover_migrations(self) -> List[Migration]:
        """Находит все миграции в директории"""
        migrations = []

        # Ищем все Python файлы в директории миграций
        for file_path in self.migrations_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue

            try:
                # Загружаем модуль миграции
                spec = importlib.util.spec_from_file_location(
                    file_path.stem, file_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Ищем класс миграции в модуле
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                            issubclass(attr, Migration) and
                            attr != Migration):
                            migrations.append(attr())
                            break

            except Exception as e:
                logger.error(f"❌ Error loading migration {file_path}: {e}")

        # Сортируем по версии
        migrations.sort(key=lambda m: m.version)
        return migrations

    async def apply_migration(self, connection: AsyncConnection, migration: Migration) -> bool:
        """Применяет одну миграцию"""
        start_time = time.time()

        try:
            logger.info(f"🔄 Applying migration: {migration}")

            # Проверяем, можно ли применить миграцию
            if not await migration.check_can_apply(connection):
                logger.warning(f"⚠️ Migration {migration.name} cannot be applied, skipping")
                return False

            # Применяем миграцию
            await migration.upgrade(connection)

            # Записываем в историю
            execution_time = time.time() - start_time
            await connection.execute(text("""
                INSERT INTO migration_history (version, name, description, execution_time)
                VALUES (:version, :name, :description, :execution_time)
            """), {
                "version": migration.version,
                "name": migration.name,
                "description": migration.get_description(),
                "execution_time": execution_time
            })

            logger.info(f"✅ Applied migration {migration.name} in {execution_time:.2f}s")
            return True

        except Exception as e:
            logger.error(f"❌ Error applying migration {migration.name}: {e}")
            raise

    async def run_migrations(self) -> None:
        """Запускает все неприменённые миграции"""
        async with self.engine.connect() as connection:
            # Начинаем транзакцию
            async with connection.begin():
                # Убеждаемся что таблица миграций существует
                await self.ensure_migration_table(connection)

                # Получаем список примененных миграций
                applied_migrations = await self.get_applied_migrations(connection)

                # Находим все доступные миграции
                all_migrations = self.discover_migrations()

                # Фильтруем неприменённые миграции
                pending_migrations = [
                    m for m in all_migrations
                    if m.version not in applied_migrations
                ]

                if not pending_migrations:
                    logger.info("✅ All migrations are up to date")
                    return

                logger.info(f"🔄 Found {len(pending_migrations)} pending migrations")

                # Применяем миграции по порядку
                for migration in pending_migrations:
                    await self.apply_migration(connection, migration)

                logger.info(f"✅ Successfully applied {len(pending_migrations)} migrations")

    async def check_column_exists(self, connection: AsyncConnection,
                                table_name: str, column_name: str) -> bool:
        """Проверяет существование столбца в таблице"""
        try:
            result = await connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                    AND column_name = :column_name
                );
            """), {"table_name": table_name, "column_name": column_name})
            return result.scalar()
        except Exception as e:
            logger.error(f"❌ Error checking column {table_name}.{column_name}: {e}")
            return False

    async def check_table_exists(self, connection: AsyncConnection, table_name: str) -> bool:
        """Проверяет существование таблицы"""
        try:
            result = await connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                );
            """), {"table_name": table_name})
            return result.scalar()
        except Exception as e:
            logger.error(f"❌ Error checking table {table_name}: {e}")
            return False
