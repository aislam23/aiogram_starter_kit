#!/bin/bash

# Интерактивная настройка нового проекта на основе aiogram_starter_kit
# Использование: ./scripts/init-project.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функция для отображения заголовка
print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              🚀 AIOGRAM STARTER KIT SETUP 🚀                ║"
    echo "║          Интерактивная настройка нового проекта              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Функция для запроса ввода с валидацией
ask_input() {
    local prompt="$1"
    local var_name="$2"
    local required="$3"
    local default="$4"
    
    while true; do
        if [ -n "$default" ]; then
            echo -e "${CYAN}$prompt${NC} ${YELLOW}[по умолчанию: $default]${NC}: "
        else
            echo -e "${CYAN}$prompt${NC}: "
        fi
        read -r input
        
        # Если введено пустое значение и есть default
        if [ -z "$input" ] && [ -n "$default" ]; then
            input="$default"
        fi
        
        # Проверка на обязательность
        if [ "$required" = "true" ] && [ -z "$input" ]; then
            echo -e "${RED}❌ Это поле обязательно для заполнения!${NC}"
            continue
        fi
        
        # Присваиваем значение переменной
        eval "$var_name='$input'"
        break
    done
}

# Функция для подтверждения
confirm() {
    local prompt="$1"
    while true; do
        echo -e "${YELLOW}$prompt${NC} ${CYAN}[y/N]${NC}: "
        read -r response
        case $response in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            "" ) return 1;;
            * ) echo -e "${RED}Пожалуйста, ответьте y или n${NC}";;
        esac
    done
}

# Основная функция
main() {
    print_header
    
    echo -e "${GREEN}Добро пожаловать в мастер настройки Aiogram бота!${NC}"
    echo -e "${BLUE}Этот скрипт поможет настроить проект под ваши нужды.${NC}"
    echo ""
    
    # Проверяем, что мы в правильной директории
    if [ ! -f "requirements.txt" ] || [ ! -f "Dockerfile" ]; then
        echo -e "${RED}❌ Ошибка: Запустите скрипт из корня проекта aiogram_starter_kit${NC}"
        exit 1
    fi
    
    # Предупреждение о Git
    if [ -d ".git" ]; then
        echo -e "${YELLOW}⚠️  Обнаружена папка .git${NC}"
        if confirm "Удалить существующую Git историю и создать новый репозиторий?"; then
            rm -rf .git
            echo -e "${GREEN}✅ Git история удалена${NC}"
        else
            echo -e "${BLUE}ℹ️  Git история сохранена${NC}"
        fi
    fi
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                    🤖 НАСТРОЙКА БОТА                          ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    # Сбор информации о боте
    ask_input "Введите токен вашего бота (от @BotFather)" "BOT_TOKEN" "true"
    ask_input "Введите username бота (без @)" "BOT_USERNAME" "true"
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                   📁 НАСТРОЙКА ПРОЕКТА                        ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    ask_input "Название проекта (для Docker volumes)" "PROJECT_NAME" "false" "my_telegram_bot"
    ask_input "Имя автора" "AUTHOR_NAME" "false" "Your Name"
    ask_input "Описание проекта" "PROJECT_DESCRIPTION" "false" "Мой Telegram бот на Aiogram"
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                   🔐 НАСТРОЙКА БЕЗОПАСНОСТИ                   ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    ask_input "Пароль для PostgreSQL" "POSTGRES_PASSWORD" "false" "securepassword"
    ask_input "Имя базы данных" "POSTGRES_DB" "false" "botdb"
    ask_input "Пользователь PostgreSQL" "POSTGRES_USER" "false" "botuser"
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                    🌐 НАСТРОЙКА ПОРТОВ                        ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    ask_input "Порт PostgreSQL (внешний)" "POSTGRES_PORT" "false" "5432"
    ask_input "Порт pgAdmin (внешний)" "PGADMIN_PORT" "false" "8080"
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                     📋 ПОДТВЕРЖДЕНИЕ                          ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    # Показываем собранную информацию
    echo -e "${CYAN}Проверьте введенные данные:${NC}"
    echo ""
    echo -e "${YELLOW}🤖 Бот:${NC}"
    echo -e "   Token: ${BOT_TOKEN:0:20}...****"
    echo -e "   Username: @$BOT_USERNAME"
    echo ""
    echo -e "${YELLOW}📁 Проект:${NC}"
    echo -e "   Название: $PROJECT_NAME"
    echo -e "   Автор: $AUTHOR_NAME"
    echo -e "   Описание: $PROJECT_DESCRIPTION"
    echo ""
    echo -e "${YELLOW}🔐 База данных:${NC}"
    echo -e "   БД: $POSTGRES_DB"
    echo -e "   Пользователь: $POSTGRES_USER"
    echo -e "   Пароль: ${POSTGRES_PASSWORD:0:3}****"
    echo ""
    echo -e "${YELLOW}🌐 Порты:${NC}"
    echo -e "   PostgreSQL: $POSTGRES_PORT"
    echo -e "   pgAdmin: $PGADMIN_PORT"
    echo ""
    
    if ! confirm "Все данные корректны? Продолжить настройку?"; then
        echo -e "${YELLOW}⏹️  Настройка отменена пользователем${NC}"
        exit 0
    fi
    
    echo ""
    echo -e "${GREEN}🔧 Начинаем настройку проекта...${NC}"
    
    # Создаем .env файл
    echo -e "${BLUE}📝 Создание .env файла...${NC}"
    cat > .env << EOF
# Bot Configuration
BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=$POSTGRES_DB
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Environment
ENV=development

# Logging
LOG_LEVEL=INFO
EOF
    
    # Обновляем docker-compose.yml с новыми портами и именами
    echo -e "${BLUE}🐳 Обновление Docker Compose...${NC}"
    
    # Заменяем порты в docker-compose.yml
    if [ "$POSTGRES_PORT" != "5432" ]; then
        sed -i.bak "s/\"5432:5432\"/\"$POSTGRES_PORT:5432\"/g" docker-compose.yml
    fi
    
    if [ "$PGADMIN_PORT" != "8080" ]; then
        sed -i.bak "s/\"8080:80\"/\"$PGADMIN_PORT:80\"/g" docker-compose.yml
    fi
    
    # Заменяем названия volumes
    if [ "$PROJECT_NAME" != "aiogram_starter_kit" ]; then
        sed -i.bak "s/aiogram_starter_kit_/${PROJECT_NAME}_/g" docker-compose.yml
        sed -i.bak "s/aiogram_starter_kit_/${PROJECT_NAME}_/g" docker-compose.prod.yml
        sed -i.bak "s/aiogram_starter_kit/$PROJECT_NAME/g" Makefile
    fi
    
    # Удаляем backup файлы
    rm -f docker-compose.yml.bak docker-compose.prod.yml.bak Makefile.bak 2>/dev/null || true
    
    # Обновляем app/__init__.py
    echo -e "${BLUE}📦 Обновление метаданных проекта...${NC}"
    cat > app/__init__.py << EOF
"""
$PROJECT_DESCRIPTION
"""

__version__ = "1.0.0"
__author__ = "$AUTHOR_NAME"
EOF
    
    # Обновляем README.md
    echo -e "${BLUE}📖 Обновление README.md...${NC}"
    sed -i.bak "s/# 🤖 Aiogram Starter Kit/# 🤖 $PROJECT_NAME/g" README.md
    sed -i.bak "1a\\
\\
> $PROJECT_DESCRIPTION\\
" README.md
    rm -f README.md.bak
    
    # Инициализируем Git если нужно
    if [ ! -d ".git" ]; then
        echo -e "${BLUE}📋 Инициализация Git репозитория...${NC}"
        git init
        git add .
        git commit -m "Initial commit: $PROJECT_NAME setup

Bot: @$BOT_USERNAME
Author: $AUTHOR_NAME
Description: $PROJECT_DESCRIPTION"
    fi
    
    # Очищаем macOS файлы
    echo -e "${BLUE}🧹 Очистка macOS артефактов...${NC}"
    find . -name ".DS_Store" -delete 2>/dev/null || true
    
    echo ""
    echo -e "${GREEN}✅ Настройка завершена успешно!${NC}"
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                    🎉 ГОТОВО К ЗАПУСКУ!                       ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}📋 Следующие шаги:${NC}"
    echo ""
    echo -e "${YELLOW}1.${NC} Запустите бота в режиме разработки:"
    echo -e "   ${GREEN}make dev-d${NC}"
    echo ""
    echo -e "${YELLOW}2.${NC} Проверьте статус сервисов:"
    echo -e "   ${GREEN}make status${NC}"
    echo ""
    echo -e "${YELLOW}3.${NC} Посмотрите логи бота:"
    echo -e "   ${GREEN}make logs-bot${NC}"
    echo ""
    echo -e "${YELLOW}4.${NC} Протестируйте бота в Telegram:"
    echo -e "   Отправьте команды: ${CYAN}/start${NC}, ${CYAN}/help${NC}, ${CYAN}/status${NC}"
    echo ""
    echo -e "${YELLOW}5.${NC} Подключите к удаленному репозиторию:"
    echo -e "   ${GREEN}git remote add origin YOUR_REPO_URL${NC}"
    echo -e "   ${GREEN}git push -u origin main${NC}"
    echo ""
    echo -e "${BLUE}🔗 Полезные ссылки:${NC}"
    echo -e "   • pgAdmin: ${CYAN}http://localhost:$PGADMIN_PORT${NC} (admin@admin.com / admin)"
    echo -e "   • PostgreSQL: ${CYAN}localhost:$POSTGRES_PORT${NC}"
    echo -e "   • Документация: ${CYAN}README.md${NC}"
    echo ""
    echo -e "${GREEN}🎯 Удачной разработки бота @$BOT_USERNAME! 🤖✨${NC}"
}

# Запуск основной функции
main "$@"
