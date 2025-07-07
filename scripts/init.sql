-- Инициализация базы данных для Telegram бота
-- Этот файл автоматически выполняется при первом запуске PostgreSQL

-- Создание таблицы пользователей
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,  -- Telegram user ID
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Создание функции для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Создание триггера для автоматического обновления updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Создание таблицы статистики бота
CREATE TABLE IF NOT EXISTS bot_stats (
    id SERIAL PRIMARY KEY,
    total_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    last_restart TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для bot_stats
CREATE INDEX IF NOT EXISTS idx_bot_stats_status ON bot_stats(status);
CREATE INDEX IF NOT EXISTS idx_bot_stats_created_at ON bot_stats(created_at);

-- Создание таблицы истории миграций
CREATE TABLE IF NOT EXISTS migration_history (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    execution_time FLOAT
);

-- Создание индекса для migration_history
CREATE INDEX IF NOT EXISTS idx_migration_history_version ON migration_history(version);

-- Вставка примера данных (только для разработки)
INSERT INTO users (id, username, first_name, last_name)
VALUES (123456789, 'test_user', 'Test', 'User')
ON CONFLICT (id) DO NOTHING;
