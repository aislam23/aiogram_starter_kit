#!/usr/bin/env python3
"""
Cross-platform production deployment script.
Usage: python scripts/deploy.py [--ci]

Flags:
    --ci    CI/CD mode (no colors, strict checks)
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path


class Colors:
    """ANSI color codes (disabled in CI mode)."""

    def __init__(self, enabled: bool = True):
        if enabled:
            self.RED = '\033[0;31m'
            self.GREEN = '\033[0;32m'
            self.YELLOW = '\033[1;33m'
            self.BLUE = '\033[0;34m'
            self.NC = '\033[0m'
        else:
            self.RED = self.GREEN = self.YELLOW = self.BLUE = self.NC = ''


def log_info(msg: str, c: Colors) -> None:
    print(f"{c.GREEN}{msg}{c.NC}")


def log_warn(msg: str, c: Colors) -> None:
    print(f"{c.YELLOW}{msg}{c.NC}")


def log_error(msg: str, c: Colors) -> None:
    print(f"{c.RED}{msg}{c.NC}")


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, check=check)


def main() -> int:
    # Determine CI mode
    ci_mode = (
        '--ci' in sys.argv or
        os.environ.get('CI') or
        os.environ.get('GITHUB_ACTIONS')
    )

    c = Colors(enabled=not ci_mode)
    docker_compose = ['docker-compose', '-f', 'docker-compose.prod.yml']

    log_info("=== Начало деплоя продакшена ===", c)

    # Check for .env.prod
    env_prod = Path('.env.prod')
    if not env_prod.exists():
        log_error("Ошибка: файл .env.prod не найден!", c)
        log_warn("Создайте его из шаблона:", c)
        print("   cp .env.prod.example .env.prod")
        print("   nano .env.prod  # или notepad .env.prod на Windows")
        return 1

    # Read and validate .env.prod
    content = env_prod.read_text(encoding='utf-8')

    # Check BOT_TOKEN
    if not re.search(r'BOT_TOKEN=.+[^_here]$', content, re.MULTILINE):
        log_error("Ошибка: установите BOT_TOKEN в .env.prod", c)
        return 1

    # Strict password check in CI mode
    if ci_mode and 'CHANGE_ME' in content:
        log_error("Ошибка: обнаружены пароли по умолчанию (CHANGE_ME) в .env.prod", c)
        log_error("Измените POSTGRES_PASSWORD и REDIS_PASSWORD на реальные значения", c)
        return 1

    # Build Docker images
    log_info("=== Сборка Docker-образов ===", c)
    result = run_command(docker_compose + ['build', '--no-cache'], check=False)
    if result.returncode != 0:
        log_error("Ошибка при сборке образов", c)
        return 1

    # Stop current containers
    log_info("=== Остановка текущих контейнеров ===", c)
    run_command(docker_compose + ['down'], check=False)

    # Start production environment
    log_info("=== Запуск продакшен-окружения ===", c)
    result = run_command(docker_compose + ['up', '-d'], check=False)
    if result.returncode != 0:
        log_error("Ошибка при запуске контейнеров", c)
        return 1

    # Wait for services to start
    log_info("=== Ожидание запуска сервисов ===", c)
    time.sleep(15)

    # Show service status
    log_info("=== Статус сервисов ===", c)
    run_command(docker_compose + ['ps'], check=False)

    # Health check
    log_info("=== Проверка здоровья ===", c)
    result = subprocess.run(
        docker_compose + ['ps'],
        capture_output=True,
        text=True
    )
    unhealthy_count = result.stdout.lower().count('unhealthy')

    if unhealthy_count > 0:
        log_error("Внимание: обнаружены нездоровые контейнеры!", c)
        run_command(docker_compose + ['ps'], check=False)

        if ci_mode:
            log_error("Последние логи бота:", c)
            run_command(docker_compose + ['logs', '--tail=30', 'bot'], check=False)
            return 1

    log_info("=== Деплой завершен успешно! ===", c)

    if not ci_mode:
        print("Просмотр логов: just logs-bot")
        print("Статус: just status")

    return 0


if __name__ == '__main__':
    sys.exit(main())
