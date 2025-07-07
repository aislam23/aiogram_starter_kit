"""
Первоначальная миграция - адаптация существующих таблиц и создание новых
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class InitialTablesMigration(Migration):
    """Миграция для адаптации существующих таблиц и создания новых"""
    
    def get_version(self) -> str:
        return "20241201_000001"
    
    def get_description(self) -> str:
        return "Adapt existing tables and create bot_stats table"
    
    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        """Проверяем, нужно ли применять миграцию"""
        # Всегда возвращаем True, чтобы миграция проверила и добавила недостающие элементы
        return True
    
    async def upgrade(self, connection: AsyncConnection) -> None:
        """Адаптация существующих таблиц и создание новых"""
        
        # Проверяем существует ли таблица users
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            );
        """))
        users_exists = result.scalar()
        
        if users_exists:
            logger.info("Table 'users' already exists, checking structure...")
            
            # Проверяем и добавляем столбец is_active если его нет
            result = await connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                    AND column_name = 'is_active'
                );
            """))
            has_is_active = result.scalar()
            
            if not has_is_active:
                logger.info("Adding is_active column to users table...")
                await connection.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
                """))
        else:
            # Создаем таблицу пользователей с правильной структурой
            logger.info("Creating users table...")
            await connection.execute(text("""
                CREATE TABLE users (
                    id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
        
        # Создаем индексы для таблицы users (только если их нет)
        logger.info("Creating indexes for users table...")
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
        """))
        
        # Пересоздаем функцию и триггер для updated_at
        await connection.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """))
        
        await connection.execute(text("""
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        """))
        await connection.execute(text("""
            CREATE TRIGGER update_users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """))
        
        # Проверяем существует ли таблица bot_stats
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'bot_stats'
            );
        """))
        bot_stats_exists = result.scalar()
        
        if not bot_stats_exists:
            # Создаем таблицу статистики бота
            logger.info("Creating bot_stats table...")
            await connection.execute(text("""
                CREATE TABLE bot_stats (
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
        
        # Проверяем существует ли таблица migration_history (может быть создана init.sql)
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'migration_history'
            );
        """))
        migration_history_exists = result.scalar()
        
        if not migration_history_exists:
            logger.info("Creating migration_history table...")
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
        
        logger.info("✅ Successfully completed initial migration")
    
    async def downgrade(self, connection: AsyncConnection) -> None:
        """Откат миграции"""
        # Не откатываем изменения в users, так как это может привести к потере данных
        await connection.execute(text("DROP TABLE IF EXISTS bot_stats CASCADE;"))
        logger.info("✅ Dropped bot_stats table") 