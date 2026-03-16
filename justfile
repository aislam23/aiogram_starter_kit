# Justfile for Aiogram Bot Docker Management
# Cross-platform alternative to Makefile
# Install: https://github.com/casey/just#installation
#   macOS:   brew install just
#   Windows: winget install Casey.Just / scoop install just
#   Linux:   cargo install just / snap install just

# Variables
project_name := "aiogram_starter_kit"

# Auto-detect Docker Compose: prefer v2 plugin, fall back to v1 standalone
docker_compose := if `docker compose version >/dev/null 2>&1; echo $?` == "0" {
    "docker compose"
} else if `command -v docker-compose >/dev/null 2>&1; echo $?` == "0" {
    "docker-compose"
} else {
    ""
}
docker_compose_prod := docker_compose + " -f docker-compose.prod.yml"

# Auto-detect Python: prefer python3, fall back to python
python := if `command -v python3 >/dev/null 2>&1; echo $?` == "0" {
    "python3"
} else if `command -v python >/dev/null 2>&1; echo $?` == "0" {
    "python"
} else {
    ""
}

# Default command - show help
default:
    @just --list

# ── Pre-flight dependency checks ────────────────────────────────

[private]
check-docker:
    #!/usr/bin/env sh
    if [ -z "{{docker_compose}}" ]; then
        echo "❌ Docker Compose не установлен."
        echo ""
        echo "Установите Docker (включает Compose v2):"
        echo "  macOS:   brew install --cask docker"
        echo "  Ubuntu:  https://docs.docker.com/engine/install/ubuntu/"
        echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"
        echo ""
        echo "Или установите docker-compose отдельно:"
        echo "  pip install docker-compose"
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        echo "❌ Docker демон не запущен."
        echo ""
        echo "Запустите Docker:"
        echo "  macOS/Windows: Откройте Docker Desktop"
        echo "  Linux:         sudo systemctl start docker"
        exit 1
    fi

[private]
check-python:
    #!/usr/bin/env sh
    if [ -z "{{python}}" ]; then
        echo "❌ Python 3 не установлен."
        echo ""
        echo "Установите Python 3:"
        echo "  macOS:   brew install python3"
        echo "  Ubuntu:  sudo apt install python3"
        echo "  Windows: https://www.python.org/downloads/"
        exit 1
    fi

[private]
check-git:
    #!/usr/bin/env sh
    if ! command -v git >/dev/null 2>&1; then
        echo "❌ Git не установлен."
        echo ""
        echo "Установите Git:"
        echo "  macOS:   brew install git  (или: xcode-select --install)"
        echo "  Ubuntu:  sudo apt install git"
        echo "  Windows: https://git-scm.com/download/win"
        exit 1
    fi

# ═══════════════════════════════════════════════════════════════
#                      DEVELOPMENT COMMANDS
# ═══════════════════════════════════════════════════════════════

# Start development environment with logs
dev: check-docker
    @echo "🚀 Starting development environment..."
    {{docker_compose}} up --build

# Start development environment in background
dev-d: check-docker
    @echo "🚀 Starting development environment in background..."
    {{docker_compose}} up --build -d

# Start development with tools (pgAdmin)
dev-tools: check-docker
    @echo "🚀 Starting development environment with tools..."
    {{docker_compose}} --profile tools up --build -d

# Stop development environment
stop: check-docker
    @echo "⏹️ Stopping development environment..."
    {{docker_compose}} down

# ═══════════════════════════════════════════════════════════════
#                    LOCAL BOT API COMMANDS
# ═══════════════════════════════════════════════════════════════

# Start with Local Bot API (2GB file limit)
dev-local: check-docker
    @echo "🚀 Starting with Local Bot API..."
    {{docker_compose}} --profile local-api up --build -d

# Start with Local Bot API (foreground with logs)
dev-local-logs: check-docker
    @echo "🚀 Starting with Local Bot API..."
    {{docker_compose}} --profile local-api up --build

# Stop Local Bot API environment
stop-local: check-docker
    @echo "⏹️ Stopping Local Bot API..."
    {{docker_compose}} --profile local-api down

# Check Local Bot API Server status
api-status:
    #!/usr/bin/env python3
    import urllib.request
    import os
    port = os.environ.get('LOCAL_API_PORT', '8081')
    try:
        urllib.request.urlopen(f'http://localhost:{port}/', timeout=2)
        print('✅ Local Bot API is running')
    except:
        print('❌ Local Bot API is not available')

# Show Local Bot API Server logs
api-logs: check-docker
    {{docker_compose}} logs -f telegram-bot-api

# Restart Local Bot API Server
api-restart: check-docker
    {{docker_compose}} restart telegram-bot-api

# ═══════════════════════════════════════════════════════════════
#                     PRODUCTION COMMANDS
# ═══════════════════════════════════════════════════════════════

# Start production environment
prod: check-docker validate-prod
    @echo "🏭 Starting production environment..."
    {{docker_compose_prod}} up --build -d

# Stop production environment
prod-stop: check-docker
    @echo "⏹️ Stopping production environment..."
    {{docker_compose_prod}} down

# Deploy to production
prod-deploy: check-docker check-python validate-prod
    @echo "🚀 Deploying to production..."
    {{python}} scripts/deploy.py

# ═══════════════════════════════════════════════════════════════
#                       CI/CD COMMANDS
# ═══════════════════════════════════════════════════════════════

# Deploy for CI/CD (no colors, strict checks)
ci-deploy: check-docker check-python
    {{python}} scripts/deploy.py --ci

# Check all services health
ci-health: check-docker
    {{docker_compose_prod}} ps
    @echo "Checking bot container..."
    {{docker_compose_prod}} exec -T bot python -c "print('Bot container: OK')"

# Show last 50 lines of bot logs
ci-logs: check-docker
    {{docker_compose_prod}} logs --tail=50 bot

# ═══════════════════════════════════════════════════════════════
#                       BUILD COMMANDS
# ═══════════════════════════════════════════════════════════════

# Build development images
build: check-docker
    @echo "🔨 Building development images..."
    {{docker_compose}} build

# Build production images
build-prod: check-docker
    @echo "🔨 Building production images..."
    {{docker_compose_prod}} build --no-cache

# ═══════════════════════════════════════════════════════════════
#                    LOGS AND MONITORING
# ═══════════════════════════════════════════════════════════════

# Show logs from all services
logs: check-docker
    {{docker_compose}} logs -f

# Show logs from bot service
logs-bot: check-docker
    {{docker_compose}} logs -f bot

# Show logs from database service
logs-db: check-docker
    {{docker_compose}} logs -f postgres

# Show logs from redis service
logs-redis: check-docker
    {{docker_compose}} logs -f redis

# ═══════════════════════════════════════════════════════════════
#                       SHELL ACCESS
# ═══════════════════════════════════════════════════════════════

# Access bot container shell
shell: check-docker
    @echo "🐚 Accessing bot container shell..."
    {{docker_compose}} exec bot bash

# Access PostgreSQL shell
db-shell: check-docker
    @echo "🗄️ Accessing PostgreSQL shell..."
    {{docker_compose}} exec postgres psql -U ${POSTGRES_USER:-botuser} -d ${POSTGRES_DB:-botdb}

# Access Redis shell
redis-shell: check-docker
    @echo "📦 Accessing Redis shell..."
    {{docker_compose}} exec redis redis-cli

# ═══════════════════════════════════════════════════════════════
#                     RESTART SERVICES
# ═══════════════════════════════════════════════════════════════

# Restart all services
restart: check-docker
    @echo "🔄 Restarting all services..."
    {{docker_compose}} restart

# Restart bot service
restart-bot: check-docker
    @echo "🔄 Restarting bot service..."
    {{docker_compose}} restart bot

# ═══════════════════════════════════════════════════════════════
#                     CLEANUP COMMANDS
# ═══════════════════════════════════════════════════════════════

# Clean up containers, volumes, and images
clean: check-docker
    @echo "🧹 Cleaning up Docker resources..."
    {{docker_compose}} down -v --remove-orphans
    docker system prune -af --volumes

# Deep clean - remove everything including volumes
clean-all: check-docker
    @echo "🧹 Deep cleaning - removing all Docker resources..."
    {{docker_compose}} down -v --remove-orphans
    {{docker_compose_prod}} down -v --remove-orphans
    docker system prune -af --volumes

# Clean macOS/Windows artifacts (.DS_Store, Thumbs.db, etc.)
clean-artifacts: check-python
    #!/usr/bin/env python3
    import os
    import pathlib

    artifacts = ['.DS_Store', 'Thumbs.db', 'desktop.ini', '._*']
    count = 0
    for pattern in artifacts:
        for f in pathlib.Path('.').rglob(pattern):
            try:
                f.unlink()
                count += 1
                print(f'Removed: {f}')
            except:
                pass
    print(f'🧹 Cleaned {count} artifacts')

# ═══════════════════════════════════════════════════════════════
#                    STATUS AND INFO
# ═══════════════════════════════════════════════════════════════

# Show status of all services
status: check-docker
    @echo "📊 Service status:"
    {{docker_compose}} ps

# Check health of all services
health: check-docker
    @echo "🏥 Health check:"
    {{docker_compose}} ps --format "table {{{{.Name}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}"

# ═══════════════════════════════════════════════════════════════
#                     SETUP COMMANDS
# ═══════════════════════════════════════════════════════════════

# Initial setup - create .env file
setup:
    #!/usr/bin/env python3
    import shutil
    import os

    if not os.path.exists('.env'):
        shutil.copy('.env.example', '.env')
        print('📄 Created .env file from .env.example')
        print('⚠️  Please edit .env file with your bot token!')
    else:
        print('📄 .env file already exists')

# Create .env.prod file for production
setup-prod:
    #!/usr/bin/env python3
    import shutil
    import os

    if not os.path.exists('.env.prod'):
        shutil.copy('.env.prod.example', '.env.prod')
        print('📄 Created .env.prod file from .env.prod.example')
        print('⚠️  Please edit .env.prod file with production values!')
        print('💡 Don\'t forget to:')
        print('  - Set strong passwords')
        print('  - Configure production bot token')
        print('  - Review all security settings')
    else:
        print('📄 .env.prod file already exists')

# Validate production environment file
validate-prod:
    #!/usr/bin/env python3
    import sys
    import os
    import re

    print('🔍 Validating production environment...')

    if not os.path.exists('.env.prod'):
        print('❌ .env.prod file not found!')
        print('💡 Run: just setup-prod')
        sys.exit(1)

    with open('.env.prod', 'r') as f:
        content = f.read()

    # Check BOT_TOKEN
    if not re.search(r'BOT_TOKEN=.+[^_here]$', content, re.MULTILINE):
        print('❌ BOT_TOKEN not set in .env.prod')
        sys.exit(1)

    # Check for default passwords
    if 'CHANGE_ME' in content:
        print('❌ Please change default passwords in .env.prod')
        sys.exit(1)

    print('✅ Production environment looks good!')

# 🚀 Interactive setup for new project (recommended!)
init-project: check-python
    @echo "🎯 Starting interactive project setup..."
    {{python}} scripts/init_project.py

# Add remote repository to existing project
setup-remote-repo: check-git
    #!/usr/bin/env python3
    import subprocess
    import sys

    repo_url = input('Enter remote repository URL: ').strip()
    if not repo_url:
        print('❌ Repository URL is required')
        sys.exit(1)

    # Check if origin exists
    result = subprocess.run(['git', 'remote', 'get-url', 'origin'],
                          capture_output=True, text=True)

    if result.returncode == 0:
        print('⚠️  Remote origin already exists')
        replace = input('Replace existing origin? [y/N]: ').strip().lower()
        if replace == 'y':
            subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url])
            print('✅ Remote origin updated')
        else:
            print('ℹ️  Keeping existing remote origin')
            sys.exit(0)
    else:
        subprocess.run(['git', 'remote', 'add', 'origin', repo_url])
        print('✅ Remote origin added')

    # Rename branch to main if needed
    result = subprocess.run(['git', 'branch', '--show-current'],
                          capture_output=True, text=True)
    if result.stdout.strip() != 'main':
        print('🔄 Renaming branch to main...')
        subprocess.run(['git', 'branch', '-M', 'main'])

    print('🚀 Pushing to remote repository...')
    result = subprocess.run(['git', 'push', '-u', 'origin', 'main'])
    if result.returncode == 0:
        print('✅ Successfully pushed to remote repository!')
    else:
        print('❌ Failed to push to remote repository')
        print('🔧 Try pushing manually: git push -u origin main')

# ═══════════════════════════════════════════════════════════════
#                        TESTING
# ═══════════════════════════════════════════════════════════════

# Run tests in bot container
test: check-docker
    @echo "🧪 Running tests..."
    {{docker_compose}} exec bot python -m pytest tests/ -v

# ═══════════════════════════════════════════════════════════════
#                   DATABASE OPERATIONS
# ═══════════════════════════════════════════════════════════════

# Create database backup
db-backup: check-docker
    #!/usr/bin/env python3
    import subprocess
    import datetime
    import os

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    user = os.environ.get('POSTGRES_USER', 'botuser')
    db = os.environ.get('POSTGRES_DB', 'botdb')
    filename = f'backup_{timestamp}.sql'

    compose_cmd = "{{docker_compose}}".split()
    print(f'💾 Creating database backup: {filename}')
    result = subprocess.run(
        compose_cmd + ['exec', '-T', 'postgres', 'pg_dump', '-U', user, db],
        capture_output=True, text=True)

    if result.returncode == 0:
        with open(filename, 'w') as f:
            f.write(result.stdout)
        print(f'✅ Backup created: {filename}')
    else:
        print(f'❌ Backup failed: {result.stderr}')

# Run database migrations
db-migrate: check-docker
    @echo "🔄 Running database migrations..."
    {{docker_compose}} exec bot python -c "import asyncio; from app.database import db; asyncio.run(db.run_migrations())"

# Show migration status
db-migration-status: check-docker
    @echo "📊 Showing migration status..."
    {{docker_compose}} exec bot python -c "import asyncio; from app.database import db; migrations = asyncio.run(db.get_migration_history()); [print(f'{m.version} - {m.name} ({m.applied_at})') for m in migrations]"

# Create new migration (usage: just create-migration migration_name "Description")
create-migration name description="": check-python
    @echo "📝 Creating migration: {{name}}"
    {{python}} scripts/create_migration.py "{{name}}" "{{description}}"

# ═══════════════════════════════════════════════════════════════
#                   UPDATE DEPENDENCIES
# ═══════════════════════════════════════════════════════════════

# Show outdated Python dependencies
update-deps: check-docker
    @echo "📦 Checking outdated dependencies..."
    {{docker_compose}} exec bot pip list --outdated
