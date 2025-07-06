"""
Первоначальная миграция - создание базовых таблиц
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class InitialTablesMigration(Migration):
    """Миграция для создания базовых таблиц пользователей и статистики"""
    
    def get_version(self) -> str:
        return "20241201_000001"
    
    def get_description(self) -> str:
        return "Create initial tables: users, bot_stats"
    
    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        """Проверяем, нужно ли создавать таблицы"""
        # Проверяем существование таблицы users
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            );
        """))
        users_exists = result.scalar()
        
        # Проверяем существование таблицы bot_stats
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'bot_stats'
            );
        """))
        bot_stats_exists = result.scalar()
        
        # Применяем миграцию только если таблицы не существуют
        return not (users_exists and bot_stats_exists)
    
    async def upgrade(self, connection: AsyncConnection) -> None:
        """Создание базовых таблиц"""
        
        # Создаем таблицу пользователей
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        
        # Создаем индексы для таблицы users
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
        """))
        
        # Создаем функцию для автоматического обновления updated_at
        await connection.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """))
        
        # Создаем триггер для автоматического обновления updated_at
        await connection.execute(text("""
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        """))
        await connection.execute(text("""
            CREATE TRIGGER update_users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """))
        
        # Создаем таблицу статистики бота
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                id SERIAL PRIMARY KEY,
                total_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                last_restart TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        
        # Создаем индексы для таблицы bot_stats
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_bot_stats_status ON bot_stats(status);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_bot_stats_created_at ON bot_stats(created_at);
        """))
        
        logger.info("✅ Created initial tables: users, bot_stats")
    
    async def downgrade(self, connection: AsyncConnection) -> None:
        """Откат миграции - удаление таблиц"""
        await connection.execute(text("DROP TABLE IF EXISTS bot_stats CASCADE;"))
        await connection.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        await connection.execute(text("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;"))
        logger.info("✅ Dropped initial tables") 