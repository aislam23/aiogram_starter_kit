"""
Флаг «заблокировал бота» у пользователей и журнал проверок живых
"""
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database.migrations.base import Migration


class AddBotBlockedAndLivenessMigration(Migration):
    """Добавляет users.bot_blocked, users.bot_blocked_at, users.last_liveness_check_at и таблицу liveness_checks"""

    def get_version(self) -> str:
        return "20260911_000001"

    def get_description(self) -> str:
        return "Add bot_blocked columns to users and liveness_checks table"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'bot_blocked'
            );
        """))
        return not result.scalar()

    async def upgrade(self, connection: AsyncConnection) -> None:
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS bot_blocked BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS bot_blocked_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS last_liveness_check_at TIMESTAMP WITH TIME ZONE;
        """))
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS liveness_checks (
                id SERIAL PRIMARY KEY,
                started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMP WITH TIME ZONE,
                trigger VARCHAR(20) NOT NULL,
                checked INTEGER NOT NULL DEFAULT 0,
                alive INTEGER NOT NULL DEFAULT 0,
                blocked INTEGER NOT NULL DEFAULT 0,
                deleted INTEGER NOT NULL DEFAULT 0,
                errors INTEGER NOT NULL DEFAULT 0,
                cancelled BOOLEAN NOT NULL DEFAULT FALSE
            );
        """))
        logger.info("✅ Added bot_blocked columns to users and liveness_checks table")

    async def downgrade(self, connection: AsyncConnection) -> None:
        await connection.execute(text("DROP TABLE IF EXISTS liveness_checks;"))
        await connection.execute(text("""
            ALTER TABLE users
            DROP COLUMN IF EXISTS bot_blocked,
            DROP COLUMN IF EXISTS bot_blocked_at,
            DROP COLUMN IF EXISTS last_liveness_check_at;
        """))
        logger.info("✅ Removed bot_blocked columns and liveness_checks table")
