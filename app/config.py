"""
Конфигурация приложения
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Bot settings
    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_username: str = Field("", alias="BOT_USERNAME")
    
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
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def database_url(self) -> str:
        """Формирование URL для подключения к базе данных"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def redis_url(self) -> str:
        """Формирование URL для подключения к Redis"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Создаем глобальный экземпляр настроек
settings = Settings()
