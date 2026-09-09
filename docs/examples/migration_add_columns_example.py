"""
Пример миграции: добавление новых столбцов
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class AddUserColumnsExampleMigration(Migration):
    """Пример миграции для добавления столбцов phone и language_code в таблицу users"""
    
    def get_version(self) -> str:
        return "20241201_000002"
    
    def get_description(self) -> str:
        return "Add phone and language_code columns to users table (example)"
    
    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        """Проверяем, нужно ли добавлять столбцы"""
        # Проверяем существование столбца phone
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'users' 
                AND column_name = 'phone'
            );
        """))
        phone_exists = result.scalar()
        
        # Проверяем существование столбца language_code
        result = await connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'users' 
                AND column_name = 'language_code'
            );
        """))
        language_code_exists = result.scalar()
        
        # Применяем миграцию только если столбцы не существуют
        return not (phone_exists and language_code_exists)
    
    async def upgrade(self, connection: AsyncConnection) -> None:
        """Добавление новых столбцов"""
        
        # Добавляем столбец phone если его нет
        await connection.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
        """))
        
        # Добавляем столбец language_code если его нет
        await connection.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS language_code VARCHAR(10) DEFAULT 'ru';
        """))
        
        # Создаем индекс для поиска по телефону
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
        """))
        
        logger.info("✅ Added phone and language_code columns to users table")
    
    async def downgrade(self, connection: AsyncConnection) -> None:
        """Откат миграции - удаление столбцов"""
        await connection.execute(text("DROP INDEX IF EXISTS idx_users_phone;"))
        await connection.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS phone;"))
        await connection.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS language_code;"))
        logger.info("✅ Removed phone and language_code columns from users table") 