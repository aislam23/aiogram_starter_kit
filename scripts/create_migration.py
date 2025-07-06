#!/usr/bin/env python3
"""
Скрипт для создания новых миграций базы данных
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def generate_migration_template(name: str, description: str) -> str:
    """Генерирует шаблон миграции"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    class_name = "".join(word.capitalize() for word in name.split("_")) + "Migration"
    
    template = f'''"""
{description}
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class {class_name}(Migration):
    """{description}"""
    
    def get_version(self) -> str:
        return "{timestamp}"
    
    def get_description(self) -> str:
        return "{description}"
    
    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        """Проверяем, нужно ли применять миграцию"""
        # TODO: Добавить проверки существования столбцов/таблиц
        return True
    
    async def upgrade(self, connection: AsyncConnection) -> None:
        """Применение миграции"""
        # TODO: Добавить SQL команды для изменения схемы
        logger.info("✅ Applied migration: {name}")
    
    async def downgrade(self, connection: AsyncConnection) -> None:
        """Откат миграции"""
        # TODO: Добавить SQL команды для отката изменений
        logger.info("✅ Reverted migration: {name}")
'''
    
    return template


def create_migration(name: str, description: str = None) -> None:
    """Создает новый файл миграции"""
    if not description:
        description = f"Migration: {name.replace('_', ' ')}"
    
    # Генерируем имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{name}.py"
    
    # Путь к директории миграций
    migrations_dir = project_root / "app" / "database" / "migrations" / "versions"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    
    # Путь к новому файлу миграции
    migration_file = migrations_dir / filename
    
    # Проверяем, что файл не существует
    if migration_file.exists():
        print(f"❌ Migration file already exists: {migration_file}")
        return
    
    # Генерируем содержимое миграции
    content = generate_migration_template(name, description)
    
    # Записываем файл
    with open(migration_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Created migration: {migration_file}")
    print(f"📝 Edit the file to add your migration logic")
    print(f"🔧 Remember to implement:")
    print(f"   - check_can_apply() method")
    print(f"   - upgrade() method")
    print(f"   - downgrade() method (optional)")


def main():
    """Главная функция"""
    if len(sys.argv) < 2:
        print("❌ Usage: python create_migration.py <migration_name> [description]")
        print("📝 Example: python create_migration.py add_user_phone 'Add phone column to users table'")
        sys.exit(1)
    
    migration_name = sys.argv[1]
    description = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Валидация имени миграции
    if not migration_name.replace('_', '').isalnum():
        print("❌ Migration name should contain only letters, numbers and underscores")
        sys.exit(1)
    
    create_migration(migration_name, description)


if __name__ == "__main__":
    main() 