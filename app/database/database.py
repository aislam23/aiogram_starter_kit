"""
Класс для работы с базой данных
"""
from datetime import datetime
from typing import List, Optional

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

from .migrations import MigrationManager
from .models import Base, BotStats, MigrationHistory, User


class Database:
    """Класс для работы с базой данных"""

    def __init__(self):
        # Преобразуем URL для асинхронной работы
        async_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

        self.engine = create_async_engine(
            async_url,
            echo=False,
            pool_pre_ping=True
        )

        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Инициализируем менеджер миграций
        self.migration_manager = MigrationManager(self.engine)

    async def run_migrations(self):
        """Запуск всех неприменённых миграций"""
        try:
            await self.migration_manager.run_migrations()
            logger.info("✅ Database migrations completed successfully")
        except Exception as e:
            logger.error(f"❌ Failed to run migrations: {e}")
            raise

    async def create_tables(self):
        """Создание таблиц в базе данных"""
        # Сначала запускаем миграции
        await self.run_migrations()

        # Затем создаем таблицы через SQLAlchemy (для новых моделей)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created successfully")

    async def add_user(self, user_id: int, username: Optional[str] = None,
                      first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        """Добавление нового пользователя"""
        async with self.session_maker() as session:
            # Проверяем, существует ли пользователь
            existing_user = await session.get(User, user_id)
            if existing_user:
                # Обновляем данные существующего пользователя
                existing_user.username = username
                existing_user.first_name = first_name
                existing_user.last_name = last_name
                existing_user.is_active = True
                existing_user.updated_at = datetime.utcnow()
                await session.commit()
                return existing_user

            # Создаем нового пользователя
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def set_admin(self, user_id: int, claimed_username: Optional[str] = None) -> None:
        """Выдать права администратора и запомнить username, по которому они выданы"""
        async with self.session_maker() as session:
            user = await session.get(User, user_id)
            if not user:
                return
            user.is_admin = True
            if claimed_username:
                user.admin_username = claimed_username.lower().lstrip("@")
            await session.commit()

    async def remove_admin(self, user_id: int) -> None:
        """Снять права администратора, выданные через бота или по username"""
        async with self.session_maker() as session:
            user = await session.get(User, user_id)
            if user:
                user.is_admin = False
                user.admin_username = None
                await session.commit()

    async def get_admins(self) -> List[User]:
        """Администраторы, отмеченные в базе (без тех, кто задан только в ADMIN_USER_IDS)"""
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.is_admin.is_(True)).order_by(User.id))
            return result.scalars().all()

    async def get_admin_by_username(self, username: str) -> Optional[User]:
        """Кто уже получил права по этому username (если кто-то получил)"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(User).where(User.is_admin.is_(True), User.admin_username == username.lower().lstrip("@"))
            )
            return result.scalars().first()

    async def get_user(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        async with self.session_maker() as session:
            return await session.get(User, user_id)

    async def get_all_users(self) -> List[User]:
        """Получение всех пользователей"""
        async with self.session_maker() as session:
            result = await session.execute(select(User))
            return result.scalars().all()

    async def get_active_users(self) -> List[User]:
        """Получение активных пользователей"""
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.is_active.is_(True)))
            return result.scalars().all()

    async def get_users_count(self) -> int:
        """Получение количества пользователей"""
        async with self.session_maker() as session:
            result = await session.execute(select(func.count(User.id)))
            return result.scalar() or 0

    async def get_active_users_count(self) -> int:
        """Получение количества активных пользователей"""
        async with self.session_maker() as session:
            result = await session.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
            return result.scalar() or 0

    async def update_bot_stats(self) -> BotStats:
        """Обновление статистики бота"""
        async with self.session_maker() as session:
            total_users = await self.get_users_count()
            active_users = await self.get_active_users_count()

            # Получаем последнюю запись статистики
            result = await session.execute(select(BotStats).order_by(BotStats.id.desc()).limit(1))
            stats = result.scalar_one_or_none()

            if stats:
                # Обновляем существующую запись
                stats.total_users = total_users
                stats.active_users = active_users
                stats.last_restart = datetime.utcnow()
            else:
                # Создаем новую запись
                stats = BotStats(
                    total_users=total_users,
                    active_users=active_users,
                    last_restart=datetime.utcnow()
                )
                session.add(stats)

            await session.commit()
            await session.refresh(stats)
            return stats

    async def get_bot_stats(self) -> Optional[BotStats]:
        """Получение статистики бота"""
        async with self.session_maker() as session:
            result = await session.execute(select(BotStats).order_by(BotStats.id.desc()).limit(1))
            return result.scalar_one_or_none()

    async def get_migration_history(self) -> List[MigrationHistory]:
        """Получение истории миграций"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(MigrationHistory).order_by(MigrationHistory.applied_at.desc())
            )
            return result.scalars().all()


# Создаем глобальный экземпляр базы данных
db = Database()
