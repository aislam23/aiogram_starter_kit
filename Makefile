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

.PHONY: help build up down logs restart clean dev prod shell db-shell redis-shell test

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

# Production commands
prod: ## Start production environment
	@echo "$(GREEN)🏭 Starting production environment...$(NC)"
	$(DOCKER_COMPOSE_PROD) up --build -d

prod-stop: ## Stop production environment
	@echo "$(YELLOW)⏹️  Stopping production environment...$(NC)"
	$(DOCKER_COMPOSE_PROD) down

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

setup-new-project: ## Prepare template for new project (removes git history)
	@echo "$(YELLOW)🚀 Preparing template for new project...$(NC)"
	@echo "$(RED)⚠️  This will remove .git directory! Press Ctrl+C to cancel$(NC)"
	@read -p "Enter new project name: " project_name; \
	if [ -d .git ]; then \
		rm -rf .git; \
		echo "$(GREEN)✅ Removed old Git history$(NC)"; \
	fi; \
	git init; \
	echo "$(GREEN)✅ Initialized new Git repository$(NC)"; \
	echo "$(BLUE)📝 Next steps:$(NC)"; \
	echo "  1. Edit .env file with your bot token"; \
	echo "  2. Update README.md with project info"; \
	echo "  3. git add . && git commit -m 'Initial commit'"; \
	echo "  4. git remote add origin your-repo-url"; \
	echo "  5. git push -u origin main"

init-project: ## 🚀 Interactive setup for new project (recommended!)
	@echo "$(GREEN)🎯 Starting interactive project setup...$(NC)"
	@./scripts/init-project.sh

# Testing
test: ## Run tests in bot container
	@echo "$(BLUE)🧪 Running tests...$(NC)"
	$(DOCKER_COMPOSE) exec bot python -m pytest tests/ -v

# Database operations
db-backup: ## Create database backup
	@echo "$(BLUE)💾 Creating database backup...$(NC)"
	$(DOCKER_COMPOSE) exec postgres pg_dump -U ${POSTGRES_USER:-botuser} ${POSTGRES_DB:-botdb} > backup_$(shell date +%Y%m%d_%H%M%S).sql

db-migrate: ## Run database migrations (placeholder)
	@echo "$(BLUE)🔄 Running database migrations...$(NC)"
	$(DOCKER_COMPOSE) exec bot python -c "print('Migrations would run here')"

# Update dependencies
update-deps: ## Update Python dependencies
	@echo "$(BLUE)📦 Updating dependencies...$(NC)"
	$(DOCKER_COMPOSE) exec bot pip list --outdated
