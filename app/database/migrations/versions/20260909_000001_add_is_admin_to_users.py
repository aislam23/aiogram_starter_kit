"""
Админы по username: столбцы is_admin и admin_username в таблице users
"""
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database.migrations.base import Migration


class AddIsAdminToUsersMigration(Migration):
    """Добавляет users.is_admin и users.admin_username"""

    def get_version(self) -> str:
        return "20260909_000001"

    def get_description(self) -> str:
        return "Add is_admin and admin_username columns to users"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'is_admin'
            );
        """))
        return not result.scalar()

    async def upgrade(self, connection: AsyncConnection) -> None:
        await connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;"))
        await connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_username VARCHAR(255);"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS idx_users_admin_username ON users(admin_username);"))
        logger.info("✅ Added is_admin and admin_username to users")

    async def downgrade(self, connection: AsyncConnection) -> None:
        await connection.execute(text("DROP INDEX IF EXISTS idx_users_admin_username;"))
        await connection.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS admin_username;"))
        await connection.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_admin;"))
        logger.info("✅ Removed is_admin and admin_username from users")
