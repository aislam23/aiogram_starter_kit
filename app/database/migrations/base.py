"""
Базовый класс для миграций базы данных
"""
from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger


class Migration(ABC):
    """Базовый класс для всех миграций"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.version = self.get_version()
    
    @abstractmethod
    def get_version(self) -> str:
        """Возвращает версию миграции в формате YYYYMMDD_HHMMSS"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Возвращает описание миграции"""
        pass
    
    @abstractmethod
    async def upgrade(self, connection: AsyncConnection) -> None:
        """Применение миграции"""
        pass
    
    async def downgrade(self, connection: AsyncConnection) -> None:
        """Откат миграции (опционально)"""
        logger.warning(f"Downgrade not implemented for migration {self.name}")
        pass
    
    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        """Проверка, можно ли применить миграцию"""
        return True
    
    def __str__(self) -> str:
        return f"{self.version}_{self.name}: {self.get_description()}"
    
    def __repr__(self) -> str:
        return f"<Migration({self.version}_{self.name})>" 