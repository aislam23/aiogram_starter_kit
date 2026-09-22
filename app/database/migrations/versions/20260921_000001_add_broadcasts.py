"""
Таблица рассылок: контент, курсор и счётчики для возобновления после рестарта
"""
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database.migrations.base import Migration


class AddBroadcastsMigration(Migration):
    """Добавляет таблицу broadcasts"""

    def get_version(self) -> str:
        return "20260921_000001"

    def get_description(self) -> str:
        return "Add broadcasts table"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'broadcasts'
            );
        """))
        return not result.scalar()

    async def upgrade(self, connection: AsyncConnection) -> None:
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
        logger.info("✅ Added broadcasts table")

    async def downgrade(self, connection: AsyncConnection) -> None:
        await connection.execute(text("DROP TABLE IF EXISTS broadcasts;"))
        logger.info("✅ Removed broadcasts table")
