# Makefile for Aiogram Bot Docker Management

# Variables
PROJECT_NAME = aiogram_starter_kit
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_PROD = docker-compose -f docker-compose.prod.yml

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

.PHONY: help build up down logs restart clean dev prod shell db-shell redis-shell test setup-remote-repo dev-local dev-local-logs stop-local api-status api-logs api-restart

help: ## Show this help message
	@echo "$(BLUE)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

# Development commands
dev: ## Start development environment
	@echo "$(GREEN)🚀 Starting development environment...$(NC)"
	$(DOCKER_COMPOSE) up --build

dev-d: ## Start development environment in background
	@echo "$(GREEN)🚀 Starting development environment in background...$(NC)"
	$(DOCKER_COMPOSE) up --build -d

dev-tools: ## Start development environment with tools (pgAdmin)
	@echo "$(GREEN)🚀 Starting development environment with tools...$(NC)"
	$(DOCKER_COMPOSE) --profile tools up --build -d

stop: ## Stop development environment
	@echo "$(YELLOW)⏹️  Stopping development environment...$(NC)"
	$(DOCKER_COMPOSE) down

# Local Bot API commands
dev-local: ## Start with Local Bot API (2GB file limit)
	@echo "$(GREEN)🚀 Starting with Local Bot API...$(NC)"
	$(DOCKER_COMPOSE) --profile local-api up --build -d

dev-local-logs: ## Start with Local Bot API (foreground)
	@echo "$(GREEN)🚀 Starting with Local Bot API...$(NC)"
	$(DOCKER_COMPOSE) --profile local-api up --build

stop-local: ## Stop Local Bot API environment
	@echo "$(YELLOW)⏹️ Stopping Local Bot API...$(NC)"
	$(DOCKER_COMPOSE) --profile local-api down

api-status: ## Check Local Bot API Server status
	@curl -sf http://localhost:$${LOCAL_API_PORT:-8081}/ >/dev/null 2>&1 && \
		echo "$(GREEN)✅ Local Bot API is running$(NC)" || \
		echo "$(RED)❌ Local Bot API is not available$(NC)"

api-logs: ## Show Local Bot API Server logs
	$(DOCKER_COMPOSE) logs -f telegram-bot-api

api-restart: ## Restart Local Bot API Server
	$(DOCKER_COMPOSE) restart telegram-bot-api

# Production commands
prod: ## Start production environment
	@echo "$(GREEN)🏭 Starting production environment...$(NC)"
	@$(MAKE) validate-prod
	$(DOCKER_COMPOSE_PROD) up --build -d

prod-stop: ## Stop production environment
	@echo "$(YELLOW)⏹️  Stopping production environment...$(NC)"
	$(DOCKER_COMPOSE_PROD) down

prod-deploy: ## Deploy to production (with validation)
	@echo "$(GREEN)🚀 Deploying to production...$(NC)"
	@$(MAKE) validate-prod
	./scripts/deploy.sh

# Build commands
build: ## Build development images
	@echo "$(BLUE)🔨 Building development images...$(NC)"
	$(DOCKER_COMPOSE) build

build-prod: ## Build production images
	@echo "$(BLUE)🔨 Building production images...$(NC)"
	$(DOCKER_COMPOSE_PROD) build --no-cache

# Logs and monitoring
logs: ## Show logs from all services
	$(DOCKER_COMPOSE) logs -f

logs-bot: ## Show logs from bot service
	$(DOCKER_COMPOSE) logs -f bot

logs-db: ## Show logs from database service
	$(DOCKER_COMPOSE) logs -f postgres

logs-redis: ## Show logs from redis service
	$(DOCKER_COMPOSE) logs -f redis

# Shell access
shell: ## Access bot container shell
	@echo "$(BLUE)🐚 Accessing bot container shell...$(NC)"
	$(DOCKER_COMPOSE) exec bot bash

db-shell: ## Access PostgreSQL shell
	@echo "$(BLUE)🗄️  Accessing PostgreSQL shell...$(NC)"
	$(DOCKER_COMPOSE) exec postgres psql -U ${POSTGRES_USER:-botuser} -d ${POSTGRES_DB:-botdb}

redis-shell: ## Access Redis shell
	@echo "$(BLUE)📦 Accessing Redis shell...$(NC)"
	$(DOCKER_COMPOSE) exec redis redis-cli

# Restart services
restart: ## Restart all services
	@echo "$(YELLOW)🔄 Restarting all services...$(NC)"
	$(DOCKER_COMPOSE) restart

restart-bot: ## Restart bot service
	@echo "$(YELLOW)🔄 Restarting bot service...$(NC)"
	$(DOCKER_COMPOSE) restart bot

# Cleanup commands
clean: ## Clean up containers, volumes, and images
	@echo "$(RED)🧹 Cleaning up Docker resources...$(NC)"
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -af --volumes

clean-all: ## Deep clean - remove everything including volumes
	@echo "$(RED)🧹 Deep cleaning - removing all Docker resources...$(NC)"
	$(DOCKER_COMPOSE) down -v --remove-orphans
	$(DOCKER_COMPOSE_PROD) down -v --remove-orphans
	docker system prune -af --volumes
	docker volume rm $(shell docker volume ls -q | grep $(PROJECT_NAME)) 2>/dev/null || true

clean-macos: ## Clean macOS artifacts (.DS_Store, etc.)
	@echo "$(YELLOW)🧹 Cleaning macOS artifacts...$(NC)"
	./scripts/clean-macos.sh

# Status and info
status: ## Show status of all services
	@echo "$(BLUE)📊 Service status:$(NC)"
	$(DOCKER_COMPOSE) ps

health: ## Check health of all services
	@echo "$(BLUE)🏥 Health check:$(NC)"
	$(DOCKER_COMPOSE) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Setup commands
setup: ## Initial setup - create .env file
	@echo "$(GREEN)⚙️  Setting up project...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)📄 Created .env file from .env.example$(NC)"; \
		echo "$(RED)⚠️  Please edit .env file with your bot token!$(NC)"; \
	else \
		echo "$(YELLOW)📄 .env file already exists$(NC)"; \
	fi

setup-git-macos: ## Setup global Git .gitignore for macOS
	@echo "$(GREEN)🍎 Setting up global Git configuration for macOS...$(NC)"
	./scripts/setup-git-macos.sh

setup-prod: ## Create .env.prod file for production
	@echo "$(GREEN)🏭 Setting up production environment...$(NC)"
	@if [ ! -f .env.prod ]; then \
		cp .env.prod.example .env.prod; \
		echo "$(YELLOW)📄 Created .env.prod file from .env.prod.example$(NC)"; \
		echo "$(RED)⚠️  Please edit .env.prod file with production values!$(NC)"; \
		echo "$(BLUE)💡 Don't forget to:$(NC)"; \
		echo "  - Set strong passwords"; \
		echo "  - Configure production bot token"; \
		echo "  - Review all security settings"; \
	else \
		echo "$(YELLOW)📄 .env.prod file already exists$(NC)"; \
	fi

validate-prod: ## Validate production environment file
	@echo "$(BLUE)🔍 Validating production environment...$(NC)"
	@if [ ! -f .env.prod ]; then \
		echo "$(RED)❌ .env.prod file not found!$(NC)"; \
		echo "$(BLUE)💡 Run: make setup-prod$(NC)"; \
		exit 1; \
	fi
	@if ! grep -q "BOT_TOKEN=.*[^_here]$$" .env.prod; then \
		echo "$(RED)❌ BOT_TOKEN not set in .env.prod$(NC)"; \
		exit 1; \
	fi
	@if grep -q "CHANGE_ME" .env.prod; then \
		echo "$(RED)❌ Please change default passwords in .env.prod$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Production environment looks good!$(NC)"

setup-new-project: ## Prepare template for new project (removes git history)
	@echo "$(YELLOW)🚀 Preparing template for new project...$(NC)"
	@echo "$(RED)⚠️  This will remove .git directory! Press Ctrl+C to cancel$(NC)"
	@read -p "Enter new project name: " project_name; \
	read -p "Enter remote repository URL (optional, press Enter to skip): " repo_url; \
	current_dir=$$(basename $$(pwd)); \
	if [ -d .git ]; then \
		rm -rf .git; \
		echo "$(GREEN)✅ Removed old Git history$(NC)"; \
	fi; \
	git init; \
	git add .; \
	git commit -m "Initial commit: $$project_name"; \
	if [ -n "$$repo_url" ]; then \
		echo "$(BLUE)📡 Setting up remote repository...$(NC)"; \
		git branch -M main; \
		git remote add origin "$$repo_url"; \
		if git push -u origin main; then \
			echo "$(GREEN)✅ Project successfully pushed to remote repository!$(NC)"; \
		else \
			echo "$(RED)❌ Failed to push to remote repository$(NC)"; \
			echo "$(BLUE)🔧 You can set it up later with:$(NC)"; \
			echo "  git remote set-url origin $$repo_url"; \
			echo "  git push -u origin main"; \
		fi; \
	else \
		echo "$(GREEN)✅ Initialized new Git repository$(NC)"; \
		echo "$(BLUE)📝 Next steps:$(NC)"; \
		echo "  1. Edit .env file with your bot token"; \
		echo "  2. Update README.md with project info"; \
		echo "  3. git remote add origin your-repo-url"; \
		echo "  4. git branch -M main"; \
		echo "  5. git push -u origin main"; \
	fi; \
	if [ "$$current_dir" != "$$project_name" ]; then \
		echo "$(BLUE)📁 Renaming project folder...$(NC)"; \
		parent_dir=$$(dirname $$(pwd)); \
		if [ -d "$$parent_dir/$$project_name" ]; then \
			echo "$(RED)❌ Folder '$$project_name' already exists!$(NC)"; \
		else \
			cd "$$parent_dir" && mv "$$current_dir" "$$project_name"; \
			echo "$(GREEN)✅ Folder renamed: $$current_dir → $$project_name$(NC)"; \
			echo "$(BLUE)📍 Project location: $$parent_dir/$$project_name$(NC)"; \
		fi; \
	fi

init-project: ## 🚀 Interactive setup for new project (recommended!)
	@echo "$(GREEN)🎯 Starting interactive project setup...$(NC)"
	@./scripts/init-project.sh

setup-remote-repo: ## Add remote repository to existing project
	@echo "$(BLUE)📡 Setting up remote repository...$(NC)"
	@read -p "Enter remote repository URL: " repo_url; \
	if [ -z "$$repo_url" ]; then \
		echo "$(RED)❌ Repository URL is required$(NC)"; \
		exit 1; \
	fi; \
	if git remote get-url origin >/dev/null 2>&1; then \
		echo "$(YELLOW)⚠️  Remote origin already exists$(NC)"; \
		read -p "Replace existing origin? [y/N]: " replace; \
		if [ "$$replace" = "y" ] || [ "$$replace" = "Y" ]; then \
			git remote set-url origin "$$repo_url"; \
			echo "$(GREEN)✅ Remote origin updated$(NC)"; \
		else \
			echo "$(BLUE)ℹ️  Keeping existing remote origin$(NC)"; \
			exit 0; \
		fi; \
	else \
		git remote add origin "$$repo_url"; \
		echo "$(GREEN)✅ Remote origin added$(NC)"; \
	fi; \
	current_branch=$$(git branch --show-current); \
	if [ "$$current_branch" != "main" ]; then \
		echo "$(BLUE)🔄 Renaming branch '$$current_branch' to 'main'...$(NC)"; \
		git branch -M main; \
	fi; \
	echo "$(YELLOW)🚀 Pushing to remote repository...$(NC)"; \
	if git push -u origin main; then \
		echo "$(GREEN)✅ Successfully pushed to remote repository!$(NC)"; \
	else \
		echo "$(RED)❌ Failed to push to remote repository$(NC)"; \
		echo "$(BLUE)🔧 Try pushing manually: git push -u origin main$(NC)"; \
	fi

# Testing
test: ## Run tests in bot container
	@echo "$(BLUE)🧪 Running tests...$(NC)"
	$(DOCKER_COMPOSE) exec bot python -m pytest tests/ -v

# Database operations
db-backup: ## Create database backup
	@echo "$(BLUE)💾 Creating database backup...$(NC)"
	$(DOCKER_COMPOSE) exec postgres pg_dump -U ${POSTGRES_USER:-botuser} ${POSTGRES_DB:-botdb} > backup_$(shell date +%Y%m%d_%H%M%S).sql

db-migrate: ## Run database migrations
	@echo "$(BLUE)🔄 Running database migrations...$(NC)"
	$(DOCKER_COMPOSE) exec bot python -c "import asyncio; from app.database import db; asyncio.run(db.run_migrations())"

db-migration-status: ## Show migration status
	@echo "$(BLUE)📊 Showing migration status...$(NC)"
	$(DOCKER_COMPOSE) exec bot python -c "import asyncio; from app.database import db; migrations = asyncio.run(db.get_migration_history()); [print(f'{m.version} - {m.name} ({m.applied_at})') for m in migrations]"

create-migration: ## Create new migration (usage: make create-migration NAME=migration_name DESC="Description")
	@if [ -z "$(NAME)" ]; then \
		echo "$(RED)❌ Please provide migration name: make create-migration NAME=migration_name DESC='Description'$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)📝 Creating migration: $(NAME)$(NC)"
	@python scripts/create_migration.py $(NAME) "$(DESC)"

# Update dependencies
update-deps: ## Update Python dependencies
	@echo "$(BLUE)📦 Updating dependencies...$(NC)"
	$(DOCKER_COMPOSE) exec bot pip list --outdated
