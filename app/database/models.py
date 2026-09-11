"""
Модели базы данных
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class User(Base):
    """Модель пользователя"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Админ, распознанный по username (ADMIN_USERNAMES). admin_username — под каким именем
    # права были выданы; не меняется при смене username, чтобы чужой не занял старое имя.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    admin_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Пользователь заблокировал бота или удалил аккаунт (my_chat_member, 403 при отправке,
    # проверка живых). Снимается, когда он снова пишет боту. «Живой» = is_active AND NOT bot_blocked.
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    bot_blocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Когда пользователя последний раз проверяли через sendChatAction (LivenessService)
    last_liveness_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class BotStats(Base):
    """Модель статистики бота"""

    __tablename__ = "bot_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    last_restart: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<BotStats(total_users={self.total_users}, status={self.status})>"


class MigrationHistory(Base):
    """Модель для отслеживания примененных миграций"""

    __tablename__ = "migration_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    execution_time: Mapped[Optional[float]] = mapped_column(nullable=True)  # время выполнения в секундах

    def __repr__(self) -> str:
        return f"<MigrationHistory(version={self.version}, name={self.name})>"


class LivenessCheck(Base):
    """Журнал прогонов проверки живых пользователей (sendChatAction)"""

    __tablename__ = "liveness_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)  # manual / scheduled
    checked: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    alive: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    blocked: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    deleted: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    errors: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # Прогон остановлен вручную или упал — такой прогон не сдвигает расписание автопроверки
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    def __repr__(self) -> str:
        return f"<LivenessCheck(id={self.id}, trigger={self.trigger}, checked={self.checked})>"
