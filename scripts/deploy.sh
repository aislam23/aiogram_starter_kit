#!/bin/bash

# Скрипт быстрого деплоя для продакшена
# Использование: ./scripts/deploy.sh

set -e

echo "🚀 Starting production deployment..."

# Проверяем наличие .env.prod
if [ ! -f .env.prod ]; then
    echo "❌ Error: .env.prod file not found!"
    echo "💡 Create it from .env.prod.example:"
    echo "   cp .env.prod.example .env.prod"
    echo "   nano .env.prod"
    exit 1
fi

# Проверяем наличие BOT_TOKEN в .env.prod
if ! grep -q "BOT_TOKEN=.*[^_here]$" .env.prod; then
    echo "❌ Error: Please set your BOT_TOKEN in .env.prod"
    exit 1
fi

echo "📋 Building production images..."
docker-compose -f docker-compose.prod.yml build --no-cache

echo "⏹️  Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down

echo "🚀 Starting production environment..."
docker-compose -f docker-compose.prod.yml up -d

echo "⏱️  Waiting for services to start..."
sleep 10

echo "📊 Checking service status..."
docker-compose -f docker-compose.prod.yml ps

echo "✅ Production deployment completed!"
echo "📝 View logs with: make logs-bot"
echo "📊 Check status with: make status"
