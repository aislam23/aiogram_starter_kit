#!/bin/bash

# Интерактивная настройка нового проекта на основе aiogram_starter_kit
# Использование: ./scripts/init-project.sh
# 
# Функциональность:
# - Настройка бота (токен, username, админ ID)
# - Конфигурация проекта (.env файлы, Docker volumes)
# - Переименование папки проекта под указанное название
# - Автоматическая привязка к удаленному Git репозиторию
# - Настройка безопасности (пароли БД, Redis)
# - Подготовка к запуску в dev/prod режимах

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
    ask_input "Введите ваш Telegram ID (для админки)" "ADMIN_ID" "true"
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                   📁 НАСТРОЙКА ПРОЕКТА                        ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    ask_input "Название проекта (для Docker volumes)" "PROJECT_NAME" "false" "my_telegram_bot"
    ask_input "Имя автора" "AUTHOR_NAME" "false" "Your Name"
    ask_input "Описание проекта" "PROJECT_DESCRIPTION" "false" "Мой Telegram бот на Aiogram"
    
    # Определяем текущее название папки проекта
    CURRENT_DIR_NAME=$(basename "$(pwd)")
    
    # Предлагаем переименовать папку под название проекта
    if [ "$CURRENT_DIR_NAME" != "$PROJECT_NAME" ]; then
        if confirm "Переименовать папку проекта с '$CURRENT_DIR_NAME' на '$PROJECT_NAME'?"; then
            RENAME_PROJECT_FOLDER="true"
        else
            RENAME_PROJECT_FOLDER="false"
        fi
    else
        RENAME_PROJECT_FOLDER="false"
    fi
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                   🔐 НАСТРОЙКА БЕЗОПАСНОСТИ                   ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    ask_input "Пароль для PostgreSQL" "POSTGRES_PASSWORD" "false" "securepassword"
    ask_input "Имя базы данных" "POSTGRES_DB" "false" "botdb"
    ask_input "Пользователь PostgreSQL" "POSTGRES_USER" "false" "botuser"
    
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                    📡 НАСТРОЙКА РЕПОЗИТОРИЯ                   ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    if confirm "Хотите привязать проект к удаленному Git репозиторию?"; then
        ask_input "Введите URL удаленного репозитория (например: git@github.com:username/repo.git)" "REPO_URL" "true"
        SETUP_REMOTE_REPO="true"
    else
        SETUP_REMOTE_REPO="false"
        echo -e "${BLUE}ℹ️  Репозиторий можно будет привязать позже вручную${NC}"
    fi
    
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
    if [ "$RENAME_PROJECT_FOLDER" = "true" ]; then
        echo -e "   Папка: $CURRENT_DIR_NAME → $PROJECT_NAME"
    fi
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
    
    if [ "$SETUP_REMOTE_REPO" = "true" ]; then
        echo -e "${YELLOW}📡 Репозиторий:${NC}"
        echo -e "   URL: $REPO_URL"
        echo ""
    fi
    
    if ! confirm "Все данные корректны? Продолжить настройку?"; then
        echo -e "${YELLOW}⏹️  Настройка отменена пользователем${NC}"
        exit 0
    fi
    
    echo ""
    echo -e "${GREEN}🔧 Начинаем настройку проекта...${NC}"
    
    # Создаем .env файл для разработки
    echo -e "${BLUE}📝 Создание .env файла для разработки...${NC}"
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

    # Создаем .env.prod файл для продакшена
    echo -e "${BLUE}📝 Создание .env.prod файла для продакшена...${NC}"
    # Генерируем случайные пароли для продакшена
    PROD_POSTGRES_PASSWORD=$(openssl rand -base64 32 2>/dev/null || date +%s | sha256sum | base64 | head -c 32)
    PROD_REDIS_PASSWORD=$(openssl rand -base64 32 2>/dev/null || date +%s | sha256sum | base64 | head -c 32)
    
    cat > .env.prod << EOF
# ========================================
# 🏭 PRODUCTION ENVIRONMENT VARIABLES
# ========================================

# 🤖 BOT CONFIGURATION
BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME

# 👑 ADMIN CONFIGURATION
ADMIN_USER_IDS=["$ADMIN_ID"]

# 🗄️ DATABASE CONFIGURATION  
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=${POSTGRES_DB}_prod
POSTGRES_USER=${POSTGRES_USER}_prod
POSTGRES_PASSWORD=$PROD_POSTGRES_PASSWORD

# 📦 REDIS CONFIGURATION
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=$PROD_REDIS_PASSWORD

# 🌍 ENVIRONMENT
ENV=production

# 📝 LOGGING
LOG_LEVEL=WARNING
EOF

    echo -e "${GREEN}✅ Созданы файлы: .env (dev) и .env.prod (production)${NC}"
    
    # Обновляем docker-compose.yml с новыми портами и именами
    echo -e "${BLUE}🐳 Обновление Docker Compose...${NC}"
    
    # Заменяем порты в docker-compose.yml
    if [ "$POSTGRES_PORT" != "5432" ]; then
        sed -i.bak "s/\"5432:5432\"/\"$POSTGRES_PORT:5432\"/g" docker-compose.yml
    fi
    
    if [ "$PGADMIN_PORT" != "8080" ]; then
        sed -i.bak "s/\"8080:80\"/\"$PGADMIN_PORT:80\"/g" docker-compose.yml
    fi
    
    # Заменяем названия volumes и контейнеров
    if [ "$PROJECT_NAME" != "aiogram_starter_kit" ]; then
        # Переименовываем volumes
        sed -i.bak "s/aiogram_starter_kit_/${PROJECT_NAME}_/g" docker-compose.yml
        sed -i.bak "s/aiogram_starter_kit_/${PROJECT_NAME}_/g" docker-compose.prod.yml
        sed -i.bak "s/aiogram_starter_kit/$PROJECT_NAME/g" Makefile
        
        echo -e "${GREEN}✅ Volumes переименованы в: ${PROJECT_NAME}_*${NC}"
    fi
    
    # Переименовываем контейнеры по имени бота (более логично)
    if [ -n "$BOT_USERNAME" ]; then
        # Создаем безопасное имя контейнера (только буквы, цифры, подчеркивания)
        SAFE_BOT_NAME=$(echo "$BOT_USERNAME" | sed 's/[^a-zA-Z0-9_]/_/g' | tr '[:upper:]' '[:lower:]')
        
        # Переименовываем контейнеры (заменяем aiogram_ на botname_)
        sed -i.bak "s/aiogram_bot_dev/${SAFE_BOT_NAME}_bot_dev/g" docker-compose.yml
        sed -i.bak "s/aiogram_redis_dev/${SAFE_BOT_NAME}_redis_dev/g" docker-compose.yml
        sed -i.bak "s/aiogram_postgres_dev/${SAFE_BOT_NAME}_postgres_dev/g" docker-compose.yml
        sed -i.bak "s/aiogram_pgadmin_dev/${SAFE_BOT_NAME}_pgadmin_dev/g" docker-compose.yml
        
        # То же для продакшена
        sed -i.bak "s/aiogram_bot_prod/${SAFE_BOT_NAME}_bot_prod/g" docker-compose.prod.yml
        sed -i.bak "s/aiogram_redis_prod/${SAFE_BOT_NAME}_redis_prod/g" docker-compose.prod.yml
        sed -i.bak "s/aiogram_postgres_prod/${SAFE_BOT_NAME}_postgres_prod/g" docker-compose.prod.yml
        
        echo -e "${GREEN}✅ Контейнеры переименованы в: ${SAFE_BOT_NAME}_*${NC}"
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
        
        # Настройка удаленного репозитория если запрошено
        if [ "$SETUP_REMOTE_REPO" = "true" ]; then
            echo -e "${BLUE}📡 Настройка удаленного репозитория...${NC}"
            git branch -M main
            git remote add origin "$REPO_URL"
            
            echo -e "${YELLOW}🚀 Отправка в удаленный репозиторий...${NC}"
            if git push -u origin main; then
                echo -e "${GREEN}✅ Проект успешно отправлен в удаленный репозиторий!${NC}"
            else
                echo -e "${RED}❌ Ошибка при отправке в удаленный репозиторий${NC}"
                echo -e "${YELLOW}💡 Возможные причины:${NC}"
                echo -e "   • Репозиторий не существует или нет доступа"
                echo -e "   • Проблемы с SSH ключами"
                echo -e "   • Неправильный URL репозитория"
                echo -e "${BLUE}🔧 Вы можете настроить репозиторий позже командами:${NC}"
                echo -e "   git remote set-url origin $REPO_URL"
                echo -e "   git push -u origin main"
            fi
        fi
    else
        # Если Git уже существует, но нужно настроить удаленный репозиторий
        if [ "$SETUP_REMOTE_REPO" = "true" ]; then
            echo -e "${BLUE}📡 Настройка удаленного репозитория для существующего Git...${NC}"
            
            # Проверяем, есть ли уже origin
            if git remote get-url origin >/dev/null 2>&1; then
                echo -e "${YELLOW}⚠️  Remote origin уже существует${NC}"
                if confirm "Заменить существующий origin на новый репозиторий?"; then
                    git remote set-url origin "$REPO_URL"
                    echo -e "${GREEN}✅ Remote origin обновлен${NC}"
                else
                    echo -e "${BLUE}ℹ️  Оставляем существующий remote origin${NC}"
                fi
            else
                git remote add origin "$REPO_URL"
                echo -e "${GREEN}✅ Remote origin добавлен${NC}"
            fi
            
            # Убеждаемся, что мы на ветке main
            current_branch=$(git branch --show-current)
            if [ "$current_branch" != "main" ]; then
                if confirm "Переименовать текущую ветку '$current_branch' в 'main'?"; then
                    git branch -M main
                    echo -e "${GREEN}✅ Ветка переименована в main${NC}"
                fi
            fi
            
            # Пушим изменения
            echo -e "${YELLOW}🚀 Отправка изменений в удаленный репозиторий...${NC}"
            if git push -u origin main; then
                echo -e "${GREEN}✅ Изменения успешно отправлены в удаленный репозиторий!${NC}"
            else
                echo -e "${RED}❌ Ошибка при отправке в удаленный репозиторий${NC}"
                echo -e "${BLUE}🔧 Попробуйте выполнить команды вручную:${NC}"
                echo -e "   git push -u origin main"
            fi
        fi
    fi
    
    # Очищаем macOS файлы
    echo -e "${BLUE}🧹 Очистка macOS артефактов...${NC}"
    find . -name ".DS_Store" -delete 2>/dev/null || true
    
    # Переименовываем папку проекта если нужно
    if [ "$RENAME_PROJECT_FOLDER" = "true" ]; then
        echo -e "${BLUE}📁 Переименование папки проекта...${NC}"
        PARENT_DIR=$(dirname "$(pwd)")
        NEW_PROJECT_PATH="$PARENT_DIR/$PROJECT_NAME"
        
        # Проверяем, не существует ли уже папка с таким именем
        if [ -d "$NEW_PROJECT_PATH" ]; then
            echo -e "${RED}❌ Папка '$PROJECT_NAME' уже существует в родительской директории!${NC}"
            echo -e "${YELLOW}💡 Попробуйте другое название проекта или переместите/переименуйте существующую папку${NC}"
        else
            # Переходим в родительскую директорию и переименовываем
            cd "$PARENT_DIR"
            if mv "$CURRENT_DIR_NAME" "$PROJECT_NAME"; then
                echo -e "${GREEN}✅ Папка проекта переименована: $CURRENT_DIR_NAME → $PROJECT_NAME${NC}"
                cd "$PROJECT_NAME"
                echo -e "${BLUE}📍 Теперь вы находитесь в: $(pwd)${NC}"
            else
                echo -e "${RED}❌ Не удалось переименовать папку проекта${NC}"
                cd "$CURRENT_DIR_NAME"  # Возвращаемся в исходную папку
            fi
        fi
    fi
    
    echo ""
    echo -e "${GREEN}✅ Настройка завершена успешно!${NC}"
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                    🎉 ГОТОВО К ЗАПУСКУ!                       ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}📋 Следующие шаги:${NC}"
    echo ""
    if [ "$RENAME_PROJECT_FOLDER" = "true" ]; then
        echo -e "${YELLOW}0.${NC} Перейдите в папку проекта (если еще не там):"
        echo -e "   ${GREEN}cd $PROJECT_NAME${NC}"
        echo ""
    fi
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
    if [ "$SETUP_REMOTE_REPO" != "true" ]; then
        echo -e "${YELLOW}5.${NC} Подключите к удаленному репозиторию:"
        echo -e "   ${GREEN}git remote add origin YOUR_REPO_URL${NC}"
        echo -e "   ${GREEN}git branch -M main${NC}"
        echo -e "   ${GREEN}git push -u origin main${NC}"
        echo ""
    fi
    echo -e "${BLUE}🔗 Полезные ссылки:${NC}"
    echo -e "   • pgAdmin: ${CYAN}http://localhost:$PGADMIN_PORT${NC} (admin@admin.com / admin)"
    echo -e "   • PostgreSQL: ${CYAN}localhost:$POSTGRES_PORT${NC}"
    echo -e "   • Документация: ${CYAN}README.md${NC}"
    if [ "$SETUP_REMOTE_REPO" = "true" ]; then
        echo -e "   • Репозиторий: ${CYAN}$REPO_URL${NC}"
    fi
    echo ""
    echo -e "${GREEN}🎯 Удачной разработки бота @$BOT_USERNAME! 🤖✨${NC}"
}

# Запуск основной функции
main "$@"
