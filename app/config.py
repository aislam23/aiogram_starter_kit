"""
Конфигурация приложения
"""
import json
from typing import Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_username(value: Optional[str]) -> str:
    """'@Artem ' → 'artem'"""
    return (value or "").strip().lstrip("@").lower()


class Settings(BaseSettings):
    """Настройки приложения"""

    # Bot settings
    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_username: str = Field("", alias="BOT_USERNAME")

    # Admin settings
    admin_user_ids: str = Field("[]", alias="ADMIN_USER_IDS")
    # Админы по username: бот запомнит их ID при первом сообщении (см. app/middlewares/user.py)
    admin_usernames: str = Field("[]", alias="ADMIN_USERNAMES")

    # Database settings
    postgres_host: str = Field("localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("botdb", alias="POSTGRES_DB")
    postgres_user: str = Field("botuser", alias="POSTGRES_USER")
    postgres_password: str = Field("", alias="POSTGRES_PASSWORD")

    # Redis settings
    redis_host: str = Field("localhost", alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    redis_db: int = Field(0, alias="REDIS_DB")
    redis_password: str = Field("", alias="REDIS_PASSWORD")

    # Environment
    env: str = Field("development", alias="ENV")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    # Файл с логами в формате JSON Lines (пустая строка — не писать в файл)
    log_file: str = Field("logs/bot.jsonl", alias="LOG_FILE")

    # Примеры хендлеров (/survey, /items) — образцы паттернов, выключите в продакшене
    example_handlers: bool = Field(False, alias="EXAMPLE_HANDLERS")

    # Часовой пояс для расписаний и отчётов (IANA, например Europe/Moscow)
    timezone: str = Field("Europe/Moscow", alias="TIMEZONE")

    # Проверка живых пользователей (app/services/liveness.py): раз в N дней ночью бот
    # шлёт sendChatAction каждому пользователю и помечает заблокировавших. 0 — только вручную из /admin
    liveness_check_interval_days: int = Field(7, alias="LIVENESS_CHECK_INTERVAL_DAYS")
    # Запросов в секунду во время прогона (делит лимит Telegram ~30/с с живым трафиком)
    liveness_rate_limit_rps: int = Field(15, alias="LIVENESS_RATE_LIMIT_RPS")

    # Local Bot API settings
    use_local_api: bool = Field(False, alias="USE_LOCAL_API")
    telegram_api_id: str = Field("", alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field("", alias="TELEGRAM_API_HASH")
    local_api_host: str = Field("telegram-bot-api", alias="LOCAL_API_HOST")
    local_api_port: int = Field(8081, alias="LOCAL_API_PORT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @validator('admin_user_ids')
    def parse_admin_ids(cls, v):
        """Парсим список админов из JSON"""
        if isinstance(v, str):
            try:
                # Пробуем парсить как JSON
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [int(user_id) for user_id in parsed]
                else:
                    # Если не список, то пробуем как строку через запятую
                    return [int(x.strip()) for x in v.split(',') if x.strip()]
            except (json.JSONDecodeError, ValueError):
                # Если не получается, пробуем как строку через запятую
                return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v

    @validator('admin_usernames')
    def parse_admin_usernames(cls, v):
        """Парсим список username админов: JSON-массив или через запятую, без @, в нижнем регистре"""
        if not isinstance(v, str):
            return v
        try:
            parsed = json.loads(v)
            items = parsed if isinstance(parsed, list) else [str(parsed)]
        except (json.JSONDecodeError, ValueError):
            items = v.split(',')
        return [normalize_username(x) for x in items if normalize_username(x)]

    def is_admin_username(self, username: Optional[str]) -> bool:
        """Есть ли username в списке админов (регистр и @ не важны)"""
        return bool(username) and normalize_username(username) in self.admin_usernames

    @property
    def database_url(self) -> str:
        """Формирование URL для подключения к базе данных"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Формирование URL для подключения к Redis"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        return user_id in self.admin_user_ids

    @property
    def local_api_url(self) -> str:
        """URL для подключения к Local Bot API Server"""
        return f"http://{self.local_api_host}:{self.local_api_port}"

    @property
    def file_upload_limit_mb(self) -> int:
        """Лимит загрузки файлов в MB"""
        return 2000 if self.use_local_api else 50

    @property
    def file_download_limit_mb(self) -> int:
        """Лимит скачивания файлов в MB"""
        return 2000 if self.use_local_api else 20

    @property
    def api_mode_name(self) -> str:
        """Человекочитаемое название режима API"""
        return "Local Bot API" if self.use_local_api else "Public Bot API"


# Создаем глобальный экземпляр настроек
settings = Settings()
