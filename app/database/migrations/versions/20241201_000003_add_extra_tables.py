"""
Миграция для добавления таблиц user_actions и broadcasts
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class AddExtraTablesMigration(Migration):
    """Миграция для добавления таблиц действий пользователей и рассылок"""
    
    def get_version(self) -> str:
        return "20241201_000003"
    
    def get_description(self) -> str:
        return "Add user_actions and broadcasts tables"
    
    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        """Проверяем, нужно ли создавать таблицы"""
        # Проверяем существование таблицы user_actions
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_actions'
            );
        """))
        user_actions_exists = result.scalar()
        
        # Проверяем существование таблицы broadcasts
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'broadcasts'
            );
        """))
        broadcasts_exists = result.scalar()
        
        # Применяем миграцию если хотя бы одной таблицы не существует
        return not (user_actions_exists and broadcasts_exists)
    
    async def upgrade(self, connection: AsyncConnection) -> None:
        """Создание таблиц для логов действий и рассылок"""
        
        # Создание таблицы для логов действий пользователей
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS user_actions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                action_type VARCHAR(50) NOT NULL,
                action_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Индексы для таблицы действий
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions(user_id);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_actions_type ON user_actions(action_type);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_actions_created_at ON user_actions(created_at);
        """))
        
        # Создание таблицы для рассылок
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id BIGSERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL,
                message_text TEXT,
                media_type VARCHAR(20),
                media_file_id TEXT,
                button_text VARCHAR(100),
                button_url TEXT,
                target_users INTEGER DEFAULT 0,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE
            );
        """))
        
        # Индексы для таблицы рассылок
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_broadcasts_admin_id ON broadcasts(admin_id);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_broadcasts_status ON broadcasts(status);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_broadcasts_created_at ON broadcasts(created_at);
        """))
        
        logger.info("✅ Created user_actions and broadcasts tables")
    
    async def downgrade(self, connection: AsyncConnection) -> None:
        """Откат миграции - удаление таблиц"""
        await connection.execute(text("DROP TABLE IF EXISTS broadcasts CASCADE;"))
        await connection.execute(text("DROP TABLE IF EXISTS user_actions CASCADE;"))
        logger.info("✅ Dropped user_actions and broadcasts tables") 