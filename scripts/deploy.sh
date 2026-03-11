#!/bin/bash

# Скрипт быстрого деплоя для продакшена
# Использование: ./scripts/deploy.sh [--ci]
#
# Флаги:
#   --ci    Режим CI/CD (без цветов, строгие проверки)

set -e

# Определяем режим CI
CI_MODE=false
if [ "$1" = "--ci" ] || [ -n "$CI" ] || [ -n "$GITHUB_ACTIONS" ]; then
    CI_MODE=true
fi

# Цвета (отключаем в CI режиме)
if [ "$CI_MODE" = true ]; then
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    NC=""
else
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
fi

log_info() {
    echo -e "${GREEN}$1${NC}"
}

log_warn() {
    echo -e "${YELLOW}$1${NC}"
}

log_error() {
    echo -e "${RED}$1${NC}"
}

log_info "=== Начало деплоя продакшена ==="

# Проверяем наличие .env.prod
if [ ! -f .env.prod ]; then
    log_error "Ошибка: файл .env.prod не найден!"
    log_warn "Создайте его из шаблона:"
    echo "   cp .env.prod.example .env.prod"
    echo "   nano .env.prod"
    exit 1
fi

# Проверяем наличие BOT_TOKEN в .env.prod
if ! grep -q "BOT_TOKEN=.*[^_here]$" .env.prod; then
    log_error "Ошибка: установите BOT_TOKEN в .env.prod"
    exit 1
fi

# Строгая проверка паролей в CI режиме
if [ "$CI_MODE" = true ]; then
    if grep -q "CHANGE_ME" .env.prod; then
        log_error "Ошибка: обнаружены пароли по умолчанию (CHANGE_ME) в .env.prod"
        log_error "Измените POSTGRES_PASSWORD и REDIS_PASSWORD на реальные значения"
        exit 1
    fi
fi

log_info "=== Сборка Docker-образов ==="
docker-compose -f docker-compose.prod.yml build --no-cache

log_info "=== Остановка текущих контейнеров ==="
docker-compose -f docker-compose.prod.yml down

log_info "=== Запуск продакшен-окружения ==="
docker-compose -f docker-compose.prod.yml up -d

log_info "=== Ожидание запуска сервисов ==="
sleep 15

log_info "=== Статус сервисов ==="
docker-compose -f docker-compose.prod.yml ps

# Проверка здоровья контейнеров
log_info "=== Проверка здоровья ==="
UNHEALTHY=$(docker-compose -f docker-compose.prod.yml ps | grep -c "unhealthy" || true)
if [ "$UNHEALTHY" -gt 0 ]; then
    log_error "Внимание: обнаружены нездоровые контейнеры!"
    docker-compose -f docker-compose.prod.yml ps
    if [ "$CI_MODE" = true ]; then
        log_error "Последние логи бота:"
        docker-compose -f docker-compose.prod.yml logs --tail=30 bot
        exit 1
    fi
fi

log_info "=== Деплой завершен успешно! ==="
if [ "$CI_MODE" = false ]; then
    echo "Просмотр логов: make logs-bot"
    echo "Статус: make status"
fi
