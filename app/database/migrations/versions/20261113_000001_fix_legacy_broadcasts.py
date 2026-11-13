"""
Чинит таблицу broadcasts на свежей базе.

Миграция 20241201_000003 создаёт broadcasts в старом формате (admin_id, ...), из-за неё 20260921_000001
считает таблицу существующей и пропускается. Бот падает на `column broadcasts.created_by does not exist`.
Здесь старая таблица заменяется новой: пустая удаляется, с данными переименовывается в broadcasts_legacy.
"""
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database.migrations.base import Migration


class FixLegacyBroadcastsMigration(Migration):
    """Заменяет broadcasts старого формата на актуальную"""

    def get_version(self) -> str:
        return "20261113_000001"

    def get_description(self) -> str:
        return "Replace legacy broadcasts table without created_by"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'broadcasts'
            ) AND NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'broadcasts' AND column_name = 'created_by'
            );
        """))
        return bool(result.scalar())

    async def upgrade(self, connection: AsyncConnection) -> None:
        rows = (await connection.execute(text("SELECT COUNT(*) FROM broadcasts;"))).scalar() or 0
        if rows:
            await connection.execute(text("ALTER TABLE broadcasts RENAME TO broadcasts_legacy;"))
            logger.warning(f"⚠️ Старая таблица broadcasts переименована в broadcasts_legacy, строк: {rows}")
        else:
            await connection.execute(text("DROP TABLE broadcasts CASCADE;"))
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id SERIAL PRIMARY KEY,
                status VARCHAR(20) NOT NULL DEFAULT 'running',
                created_by BIGINT NOT NULL,
                content TEXT NOT NULL,
                button_text VARCHAR(255),
                button_url VARCHAR(2048),
                total INTEGER NOT NULL DEFAULT 0,
                last_user_id BIGINT NOT NULL DEFAULT 0,
                sent INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                blocked INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMP WITH TIME ZONE
            );
        """))
        logger.info("✅ Таблица broadcasts приведена к актуальному формату")

    async def downgrade(self, connection: AsyncConnection) -> None:
        # Откат не нужен: старый формат таблицы кодом не используется
        pass
