# Justfile for Aiogram Bot Docker Management
# Cross-platform alternative to Makefile
# Install: https://github.com/casey/just#installation
#   macOS:   brew install just
#   Windows: winget install Casey.Just / scoop install just
#   Linux:   cargo install just / snap install just

# Variables
project_name := "aiogram_starter_kit"
docker_compose := "docker-compose"
docker_compose_prod := "docker-compose -f docker-compose.prod.yml"

# Default command - show help
default:
    @just --list

# ═══════════════════════════════════════════════════════════════
#                      DEVELOPMENT COMMANDS
# ═══════════════════════════════════════════════════════════════

# Start development environment with logs
dev:
    @echo "🚀 Starting development environment..."
    {{docker_compose}} up --build

# Start development environment in background
dev-d:
    @echo "🚀 Starting development environment in background..."
    {{docker_compose}} up --build -d

# Start development with tools (pgAdmin)
dev-tools:
    @echo "🚀 Starting development environment with tools..."
    {{docker_compose}} --profile tools up --build -d

# Stop development environment
stop:
    @echo "⏹️ Stopping development environment..."
    {{docker_compose}} down

# ═══════════════════════════════════════════════════════════════
#                    LOCAL BOT API COMMANDS
# ═══════════════════════════════════════════════════════════════

# Start with Local Bot API (2GB file limit)
dev-local:
    @echo "🚀 Starting with Local Bot API..."
    {{docker_compose}} --profile local-api up --build -d

# Start with Local Bot API (foreground with logs)
dev-local-logs:
    @echo "🚀 Starting with Local Bot API..."
    {{docker_compose}} --profile local-api up --build

# Stop Local Bot API environment
stop-local:
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
api-logs:
    {{docker_compose}} logs -f telegram-bot-api

# Restart Local Bot API Server
api-restart:
    {{docker_compose}} restart telegram-bot-api

# ═══════════════════════════════════════════════════════════════
#                     PRODUCTION COMMANDS
# ═══════════════════════════════════════════════════════════════

# Start production environment
prod: validate-prod
    @echo "🏭 Starting production environment..."
    {{docker_compose_prod}} up --build -d

# Stop production environment
prod-stop:
    @echo "⏹️ Stopping production environment..."
    {{docker_compose_prod}} down

# Deploy to production
prod-deploy: validate-prod
    @echo "🚀 Deploying to production..."
    python scripts/deploy.py

# ═══════════════════════════════════════════════════════════════
#                       CI/CD COMMANDS
# ═══════════════════════════════════════════════════════════════

# Deploy for CI/CD (no colors, strict checks)
ci-deploy:
    python scripts/deploy.py --ci

# Check all services health
ci-health:
    {{docker_compose_prod}} ps
    @echo "Checking bot container..."
    {{docker_compose_prod}} exec -T bot python -c "print('Bot container: OK')"

# Show last 50 lines of bot logs
ci-logs:
    {{docker_compose_prod}} logs --tail=50 bot

# ═══════════════════════════════════════════════════════════════
#                       BUILD COMMANDS
# ═══════════════════════════════════════════════════════════════

# Build development images
build:
    @echo "🔨 Building development images..."
    {{docker_compose}} build

# Build production images
build-prod:
    @echo "🔨 Building production images..."
    {{docker_compose_prod}} build --no-cache

# ═══════════════════════════════════════════════════════════════
#                    LOGS AND MONITORING
# ═══════════════════════════════════════════════════════════════

# Show logs from all services
logs:
    {{docker_compose}} logs -f

# Show logs from bot service
logs-bot:
    {{docker_compose}} logs -f bot

# Show logs from database service
logs-db:
    {{docker_compose}} logs -f postgres

# Show logs from redis service
logs-redis:
    {{docker_compose}} logs -f redis

# ═══════════════════════════════════════════════════════════════
#                       SHELL ACCESS
# ═══════════════════════════════════════════════════════════════

# Access bot container shell
shell:
    @echo "🐚 Accessing bot container shell..."
    {{docker_compose}} exec bot bash

# Access PostgreSQL shell
db-shell:
    @echo "🗄️ Accessing PostgreSQL shell..."
    {{docker_compose}} exec postgres psql -U ${POSTGRES_USER:-botuser} -d ${POSTGRES_DB:-botdb}

# Access Redis shell
redis-shell:
    @echo "📦 Accessing Redis shell..."
    {{docker_compose}} exec redis redis-cli

# ═══════════════════════════════════════════════════════════════
#                     RESTART SERVICES
# ═══════════════════════════════════════════════════════════════

# Restart all services
restart:
    @echo "🔄 Restarting all services..."
    {{docker_compose}} restart

# Restart bot service
restart-bot:
    @echo "🔄 Restarting bot service..."
    {{docker_compose}} restart bot

# ═══════════════════════════════════════════════════════════════
#                     CLEANUP COMMANDS
# ═══════════════════════════════════════════════════════════════

# Clean up containers, volumes, and images
clean:
    @echo "🧹 Cleaning up Docker resources..."
    {{docker_compose}} down -v --remove-orphans
    docker system prune -af --volumes

# Deep clean - remove everything including volumes
clean-all:
    @echo "🧹 Deep cleaning - removing all Docker resources..."
    {{docker_compose}} down -v --remove-orphans
    {{docker_compose_prod}} down -v --remove-orphans
    docker system prune -af --volumes

# Clean macOS/Windows artifacts (.DS_Store, Thumbs.db, etc.)
clean-artifacts:
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
status:
    @echo "📊 Service status:"
    {{docker_compose}} ps

# Check health of all services
health:
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
init-project:
    @echo "🎯 Starting interactive project setup..."
    python scripts/init_project.py

# Add remote repository to existing project
setup-remote-repo:
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
test:
    @echo "🧪 Running tests..."
    {{docker_compose}} exec bot python -m pytest tests/ -v

# ═══════════════════════════════════════════════════════════════
#                   DATABASE OPERATIONS
# ═══════════════════════════════════════════════════════════════

# Create database backup
db-backup:
    #!/usr/bin/env python3
    import subprocess
    import datetime
    import os

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    user = os.environ.get('POSTGRES_USER', 'botuser')
    db = os.environ.get('POSTGRES_DB', 'botdb')
    filename = f'backup_{timestamp}.sql'

    print(f'💾 Creating database backup: {filename}')
    result = subprocess.run([
        'docker-compose', 'exec', '-T', 'postgres',
        'pg_dump', '-U', user, db
    ], capture_output=True, text=True)

    if result.returncode == 0:
        with open(filename, 'w') as f:
            f.write(result.stdout)
        print(f'✅ Backup created: {filename}')
    else:
        print(f'❌ Backup failed: {result.stderr}')

# Run database migrations
db-migrate:
    @echo "🔄 Running database migrations..."
    {{docker_compose}} exec bot python -c "import asyncio; from app.database import db; asyncio.run(db.run_migrations())"

# Show migration status
db-migration-status:
    @echo "📊 Showing migration status..."
    {{docker_compose}} exec bot python -c "import asyncio; from app.database import db; migrations = asyncio.run(db.get_migration_history()); [print(f'{m.version} - {m.name} ({m.applied_at})') for m in migrations]"

# Create new migration (usage: just create-migration migration_name "Description")
create-migration name description="":
    @echo "📝 Creating migration: {{name}}"
    python scripts/create_migration.py "{{name}}" "{{description}}"

# ═══════════════════════════════════════════════════════════════
#                   UPDATE DEPENDENCIES
# ═══════════════════════════════════════════════════════════════

# Show outdated Python dependencies
update-deps:
    @echo "📦 Checking outdated dependencies..."
    {{docker_compose}} exec bot pip list --outdated
