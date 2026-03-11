#!/usr/bin/env python3
"""
Cross-platform interactive project setup for aiogram_starter_kit.
Usage: python scripts/init_project.py

Features:
- Bot configuration (token, username, admin ID)
- Project setup (.env files, Docker volumes)
- Folder renaming to match project name
- Remote Git repository setup
- Security settings (DB passwords, Redis)
- Preparation for dev/prod modes
"""

import os
import re
import secrets
import shutil
import socket
import string
import subprocess
import sys
from pathlib import Path
from typing import Optional


class Colors:
    """ANSI color codes for terminal output."""

    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

    @classmethod
    def disable(cls) -> None:
        """Disable colors (for Windows without ANSI support)."""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = ''
        cls.PURPLE = cls.CYAN = cls.NC = ''


# Enable ANSI colors on Windows 10+
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        Colors.disable()


def print_header() -> None:
    """Print welcome header."""
    c = Colors
    print(f"{c.BLUE}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║              🚀 AIOGRAM STARTER KIT SETUP 🚀                ║")
    print("║          Интерактивная настройка нового проекта              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{c.NC}")


def ask_input(prompt: str, required: bool = False, default: str = "") -> str:
    """Ask for user input with optional default value."""
    c = Colors

    while True:
        if default:
            display = f"{c.CYAN}{prompt}{c.NC} {c.YELLOW}[по умолчанию: {default}]{c.NC}: "
        else:
            display = f"{c.CYAN}{prompt}{c.NC}: "

        try:
            value = input(display).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{c.YELLOW}⏹️ Настройка отменена{c.NC}")
            sys.exit(0)

        if not value and default:
            return default

        if required and not value:
            print(f"{c.RED}❌ Это поле обязательно для заполнения!{c.NC}")
            continue

        return value


def confirm(prompt: str) -> bool:
    """Ask for yes/no confirmation."""
    c = Colors

    while True:
        try:
            response = input(f"{c.YELLOW}{prompt}{c.NC} {c.CYAN}[y/N]{c.NC}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False

        if response in ('y', 'yes', 'д', 'да'):
            return True
        if response in ('n', 'no', 'н', 'нет', ''):
            return False

        print(f"{c.RED}Пожалуйста, ответьте y или n{c.NC}")


def generate_password(length: int = 15) -> str:
    """Generate a random alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return False
        except OSError:
            return True


def find_free_port(start_port: int, max_attempts: int = 10) -> int:
    """Find a free port starting from start_port."""
    port = start_port
    for _ in range(max_attempts):
        if not is_port_in_use(port):
            return port
        port += 1
    return start_port


def parse_bot_username(input_str: str) -> str:
    """Extract bot username from various formats."""
    input_str = input_str.strip()

    # https://t.me/username or t.me/username
    match = re.match(r'^(?:https?://)?t\.me/([a-zA-Z0-9_]+)$', input_str)
    if match:
        return match.group(1)

    # @username
    if input_str.startswith('@'):
        return input_str[1:]

    return input_str


def validate_bot_username(username: str) -> bool:
    """Validate bot username format."""
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', username))


def ask_bot_username() -> str:
    """Ask for bot username with parsing and validation."""
    c = Colors

    while True:
        raw = ask_input("Введите username бота (можно @username или https://t.me/username)", required=True)
        username = parse_bot_username(raw)

        if not validate_bot_username(username):
            print(f"{c.RED}❌ Некорректный username. "
                  f"Должен начинаться с буквы, содержать 5-32 символа (буквы, цифры, _){c.NC}")
            continue

        print(f"{c.GREEN}✅ Username бота: @{username}{c.NC}")
        return username


def run_git(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a git command."""
    cmd = ['git'] + list(args)
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    return subprocess.run(cmd, check=check)


def replace_in_file(filepath: Path, old: str, new: str) -> None:
    """Replace text in a file."""
    if not filepath.exists():
        return
    content = filepath.read_text(encoding='utf-8')
    content = content.replace(old, new)
    filepath.write_text(content, encoding='utf-8')


def main() -> int:
    c = Colors
    print_header()

    print(f"{c.GREEN}Добро пожаловать в мастер настройки Aiogram бота!{c.NC}")
    print(f"{c.BLUE}Этот скрипт поможет настроить проект под ваши нужды.{c.NC}")
    print()

    # Check we're in the right directory
    if not Path('requirements.txt').exists() or not Path('Dockerfile').exists():
        print(f"{c.RED}❌ Ошибка: Запустите скрипт из корня проекта aiogram_starter_kit{c.NC}")
        return 1

    # Git warning
    if Path('.git').exists():
        print(f"{c.YELLOW}⚠️  Обнаружена папка .git{c.NC}")
        if confirm("Удалить существующую Git историю и создать новый репозиторий?"):
            shutil.rmtree('.git')
            print(f"{c.GREEN}✅ Git история удалена{c.NC}")
        else:
            print(f"{c.BLUE}ℹ️  Git история сохранена{c.NC}")

    # ═══════════════════════════════════════════════════════════
    #                    BOT CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    print()
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print(f"{c.PURPLE}                    🤖 НАСТРОЙКА БОТА                          {c.NC}")
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")

    bot_token = ask_input("Введите токен вашего бота (от @BotFather)", required=True)
    bot_username = ask_bot_username()
    admin_id = ask_input("Введите ваш Telegram ID (для админки)", required=True)

    # ═══════════════════════════════════════════════════════════
    #                   PROJECT CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    print()
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print(f"{c.PURPLE}                   📁 НАСТРОЙКА ПРОЕКТА                        {c.NC}")
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")

    project_name = ask_input("Название проекта (для Docker volumes)", default="my_telegram_bot")
    author_name = ask_input("Имя автора", default="Your Name")
    project_description = ask_input("Описание проекта", default="Мой Telegram бот на Aiogram")

    current_dir_name = Path.cwd().name
    rename_folder = False
    if current_dir_name != project_name:
        rename_folder = confirm(f"Переименовать папку проекта с '{current_dir_name}' на '{project_name}'?")

    # ═══════════════════════════════════════════════════════════
    #                  SECURITY CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    print()
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print(f"{c.PURPLE}                   🔐 НАСТРОЙКА БЕЗОПАСНОСТИ                   {c.NC}")
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")

    postgres_password = generate_password(15)
    print(f"{c.GREEN}🔑 Сгенерирован случайный пароль PostgreSQL (15 символов){c.NC}")

    # Safe project name for DB
    safe_project_name = re.sub(r'[^a-z0-9_]', '_', project_name.lower())
    default_db_name = f"{safe_project_name}_db"
    default_db_user = f"{safe_project_name}_user"

    postgres_db = ask_input("Имя базы данных", default=default_db_name)
    postgres_user = ask_input("Пользователь PostgreSQL", default=default_db_user)

    # ═══════════════════════════════════════════════════════════
    #                  REPOSITORY CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    print()
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print(f"{c.PURPLE}                    📡 НАСТРОЙКА РЕПОЗИТОРИЯ                   {c.NC}")
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")

    setup_remote_repo = False
    create_new_repo = False
    repo_url: Optional[str] = None
    gh_repo_name = ""
    gh_repo_desc = ""
    gh_visibility = "private"

    if confirm("Хотите привязать проект к Git репозиторию?"):
        print()
        print(f"{c.CYAN}Выберите способ:{c.NC}")
        print(f"  {c.YELLOW}1){c.NC} Создать новый репозиторий через GitHub CLI (gh)")
        print(f"  {c.YELLOW}2){c.NC} Указать URL существующего репозитория")
        print()

        choice = ask_input("Ваш выбор [1/2]", default="2")

        if choice == "1":
            # Check for gh CLI
            gh_check = subprocess.run(['gh', '--version'], capture_output=True)
            if gh_check.returncode != 0:
                print(f"{c.RED}❌ GitHub CLI (gh) не установлен!{c.NC}")
                print(f"{c.BLUE}💡 Установите gh:{c.NC}")
                print(f"   macOS: {c.GREEN}brew install gh{c.NC}")
                print(f"   Windows: {c.GREEN}winget install GitHub.cli{c.NC}")
                print(f"   Linux: {c.GREEN}https://github.com/cli/cli#installation{c.NC}")
                print()
                if confirm("Указать URL существующего репозитория вместо этого?"):
                    repo_url = ask_input("Введите URL репозитория", required=True)
                    setup_remote_repo = True
            else:
                # Check gh auth
                auth_check = subprocess.run(['gh', 'auth', 'status'], capture_output=True)
                if auth_check.returncode != 0:
                    print(f"{c.YELLOW}⚠️  GitHub CLI не авторизован{c.NC}")
                    print(f"{c.BLUE}Запускаем авторизацию...{c.NC}")
                    auth_result = subprocess.run(['gh', 'auth', 'login'])
                    if auth_result.returncode != 0:
                        print(f"{c.RED}❌ Не удалось авторизоваться в GitHub CLI{c.NC}")
                        if confirm("Указать URL существующего репозитория вместо этого?"):
                            repo_url = ask_input("Введите URL репозитория", required=True)
                            setup_remote_repo = True
                    else:
                        create_new_repo = True
                else:
                    create_new_repo = True

                if create_new_repo:
                    gh_repo_name = ask_input("Название репозитория на GitHub", default=project_name)
                    gh_repo_desc = ask_input("Описание репозитория", default=project_description)

                    print()
                    print(f"{c.CYAN}Тип репозитория:{c.NC}")
                    print(f"  {c.YELLOW}1){c.NC} Приватный (private) - рекомендуется")
                    print(f"  {c.YELLOW}2){c.NC} Публичный (public)")
                    print()

                    vis_choice = ask_input("Ваш выбор [1/2]", default="1")
                    gh_visibility = "public" if vis_choice == "2" else "private"
                    setup_remote_repo = True

        elif choice == "2":
            repo_url = ask_input("Введите URL репозитория (например: git@github.com:username/repo.git)", required=True)
            setup_remote_repo = True
    else:
        print(f"{c.BLUE}ℹ️  Репозиторий можно будет привязать позже вручную{c.NC}")

    # ═══════════════════════════════════════════════════════════
    #                     PORT CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    print()
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print(f"{c.PURPLE}                    🌐 НАСТРОЙКА ПОРТОВ                        {c.NC}")
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")

    print(f"{c.BLUE}🔍 Проверка доступности портов...{c.NC}")

    # PostgreSQL port
    default_pg_port = 5432
    suggested_pg_port = find_free_port(default_pg_port)
    if suggested_pg_port != default_pg_port:
        print(f"{c.YELLOW}⚠️  Порт {default_pg_port} занят, предлагается: {suggested_pg_port}{c.NC}")
    else:
        print(f"{c.GREEN}✅ Порт PostgreSQL {default_pg_port} свободен{c.NC}")

    # pgAdmin port
    default_pgadmin_port = 8080
    suggested_pgadmin_port = find_free_port(default_pgadmin_port)
    if suggested_pgadmin_port != default_pgadmin_port:
        print(f"{c.YELLOW}⚠️  Порт {default_pgadmin_port} занят, предлагается: {suggested_pgadmin_port}{c.NC}")
    else:
        print(f"{c.GREEN}✅ Порт pgAdmin {default_pgadmin_port} свободен{c.NC}")

    print()
    postgres_port = ask_input("Порт PostgreSQL (внешний)", default=str(suggested_pg_port))
    pgadmin_port = ask_input("Порт pgAdmin (внешний)", default=str(suggested_pgadmin_port))

    # ═══════════════════════════════════════════════════════════
    #                       CONFIRMATION
    # ═══════════════════════════════════════════════════════════
    print()
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print(f"{c.PURPLE}                     📋 ПОДТВЕРЖДЕНИЕ                          {c.NC}")
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")

    print(f"{c.CYAN}Проверьте введенные данные:{c.NC}")
    print()
    print(f"{c.YELLOW}🤖 Бот:{c.NC}")
    print(f"   Token: {bot_token[:20]}...****")
    print(f"   Username: @{bot_username}")
    print()
    print(f"{c.YELLOW}📁 Проект:{c.NC}")
    print(f"   Название: {project_name}")
    print(f"   Автор: {author_name}")
    print(f"   Описание: {project_description}")
    if rename_folder:
        print(f"   Папка: {current_dir_name} → {project_name}")
    print()
    print(f"{c.YELLOW}🔐 База данных:{c.NC}")
    print(f"   БД: {postgres_db}")
    print(f"   Пользователь: {postgres_user}")
    print(f"   Пароль: {postgres_password[:3]}****")
    print()
    print(f"{c.YELLOW}🌐 Порты:{c.NC}")
    print(f"   PostgreSQL: {postgres_port}")
    print(f"   pgAdmin: {pgadmin_port}")
    print()

    if setup_remote_repo:
        print(f"{c.YELLOW}📡 Репозиторий:{c.NC}")
        if create_new_repo:
            print(f"   Создать: {gh_repo_name} ({gh_visibility})")
            print(f"   Описание: {gh_repo_desc}")
        else:
            print(f"   URL: {repo_url}")
        print()

    if not confirm("Все данные корректны? Продолжить настройку?"):
        print(f"{c.YELLOW}⏹️  Настройка отменена пользователем{c.NC}")
        return 0

    print()
    print(f"{c.GREEN}🔧 Начинаем настройку проекта...{c.NC}")

    # ═══════════════════════════════════════════════════════════
    #                    CREATE .env FILES
    # ═══════════════════════════════════════════════════════════
    print(f"{c.BLUE}📝 Создание .env файла для разработки...{c.NC}")

    env_content = f"""# Bot Configuration
BOT_TOKEN={bot_token}
BOT_USERNAME={bot_username}

# Admin Configuration
ADMIN_USER_IDS=[{admin_id}]

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB={postgres_db}
POSTGRES_USER={postgres_user}
POSTGRES_PASSWORD={postgres_password}

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Environment
ENV=development

# Logging
LOG_LEVEL=INFO
"""
    Path('.env').write_text(env_content, encoding='utf-8')

    # Production .env file
    print(f"{c.BLUE}📝 Создание .env.prod файла для продакшена...{c.NC}")

    prod_postgres_password = generate_password(32)
    prod_redis_password = generate_password(32)

    env_prod_content = f"""# ========================================
# 🏭 PRODUCTION ENVIRONMENT VARIABLES
# ========================================

# 🤖 BOT CONFIGURATION
BOT_TOKEN={bot_token}
BOT_USERNAME={bot_username}

# 👑 ADMIN CONFIGURATION
ADMIN_USER_IDS=["{admin_id}"]

# 🗄️ DATABASE CONFIGURATION
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB={postgres_db}_prod
POSTGRES_USER={postgres_user}_prod
POSTGRES_PASSWORD={prod_postgres_password}

# 📦 REDIS CONFIGURATION
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD={prod_redis_password}

# 🌍 ENVIRONMENT
ENV=production

# 📝 LOGGING
LOG_LEVEL=WARNING
"""
    Path('.env.prod').write_text(env_prod_content, encoding='utf-8')
    print(f"{c.GREEN}✅ Созданы файлы: .env (dev) и .env.prod (production){c.NC}")

    # ═══════════════════════════════════════════════════════════
    #                 UPDATE DOCKER COMPOSE
    # ═══════════════════════════════════════════════════════════
    print(f"{c.BLUE}🐳 Обновление Docker Compose...{c.NC}")

    docker_compose = Path('docker-compose.yml')
    docker_compose_prod = Path('docker-compose.prod.yml')
    makefile = Path('Makefile')
    justfile = Path('justfile')

    # Update ports
    if postgres_port != "5432":
        replace_in_file(docker_compose, '"5432:5432"', f'"{postgres_port}:5432"')

    if pgadmin_port != "8080":
        replace_in_file(docker_compose, '"8080:80"', f'"{pgadmin_port}:80"')

    # Rename volumes and containers
    if project_name != "aiogram_starter_kit":
        replace_in_file(docker_compose, 'aiogram_starter_kit_', f'{project_name}_')
        replace_in_file(docker_compose_prod, 'aiogram_starter_kit_', f'{project_name}_')
        replace_in_file(makefile, 'aiogram_starter_kit', project_name)
        replace_in_file(justfile, 'aiogram_starter_kit', project_name)
        print(f"{c.GREEN}✅ Volumes переименованы в: {project_name}_*{c.NC}")

    # Rename containers to bot name
    if bot_username:
        safe_bot_name = re.sub(r'[^a-zA-Z0-9_]', '_', bot_username).lower()

        for prefix in ['aiogram_bot', 'aiogram_redis', 'aiogram_postgres', 'aiogram_pgadmin']:
            replace_in_file(docker_compose, f'{prefix}_dev', f'{safe_bot_name}_{prefix.split("_")[1]}_dev')

        for prefix in ['aiogram_bot', 'aiogram_redis', 'aiogram_postgres']:
            replace_in_file(docker_compose_prod, f'{prefix}_prod', f'{safe_bot_name}_{prefix.split("_")[1]}_prod')

        print(f"{c.GREEN}✅ Контейнеры переименованы в: {safe_bot_name}_*{c.NC}")

    # ═══════════════════════════════════════════════════════════
    #                 UPDATE PROJECT METADATA
    # ═══════════════════════════════════════════════════════════
    print(f"{c.BLUE}📦 Обновление метаданных проекта...{c.NC}")

    app_init = Path('app/__init__.py')
    app_init.write_text(f'''"""
{project_description}
"""

__version__ = "1.0.0"
__author__ = "{author_name}"
''', encoding='utf-8')

    # Update README.md
    print(f"{c.BLUE}📖 Обновление README.md...{c.NC}")
    readme = Path('README.md')
    if readme.exists():
        content = readme.read_text(encoding='utf-8')
        content = content.replace('# 🤖 Aiogram Starter Kit', f'# 🤖 {project_name}')
        # Add description after title
        lines = content.split('\n')
        if len(lines) > 0:
            lines.insert(1, f'\n> {project_description}\n')
            content = '\n'.join(lines)
        readme.write_text(content, encoding='utf-8')

    # ═══════════════════════════════════════════════════════════
    #                    INITIALIZE GIT
    # ═══════════════════════════════════════════════════════════
    if not Path('.git').exists():
        print(f"{c.BLUE}📋 Инициализация Git репозитория...{c.NC}")
        run_git('init')
        run_git('add', '.')
        run_git('commit', '-m', f'''Initial commit: {project_name} setup

Bot: @{bot_username}
Author: {author_name}
Description: {project_description}''')
        run_git('branch', '-M', 'main')

    # ═══════════════════════════════════════════════════════════
    #                 SETUP REMOTE REPOSITORY
    # ═══════════════════════════════════════════════════════════
    if setup_remote_repo:
        print(f"{c.BLUE}📡 Настройка удаленного репозитория...{c.NC}")

        if create_new_repo:
            print(f"{c.YELLOW}🚀 Создание репозитория на GitHub...{c.NC}")

            cmd = ['gh', 'repo', 'create', gh_repo_name, f'--{gh_visibility}',
                   '--source=.', '--remote=origin', '--push']
            if gh_repo_desc:
                cmd.extend(['--description', gh_repo_desc])

            result = subprocess.run(cmd)
            if result.returncode == 0:
                # Get repo URL
                url_result = subprocess.run(
                    ['gh', 'repo', 'view', '--json', 'url', '-q', '.url'],
                    capture_output=True, text=True
                )
                repo_url = url_result.stdout.strip() if url_result.returncode == 0 else None
                print(f"{c.GREEN}✅ Репозиторий успешно создан и код отправлен!{c.NC}")
                if repo_url:
                    print(f"{c.CYAN}🔗 URL: {repo_url}{c.NC}")
            else:
                print(f"{c.RED}❌ Ошибка при создании репозитория{c.NC}")
                print(f"{c.YELLOW}💡 Возможные причины:{c.NC}")
                print("   • Репозиторий с таким именем уже существует")
                print("   • Проблемы с авторизацией gh")
        else:
            # Existing repo - add origin
            result = run_git('remote', 'get-url', 'origin', check=False, capture=True)
            if result.returncode == 0:
                print(f"{c.YELLOW}⚠️  Remote origin уже существует{c.NC}")
                if confirm("Заменить существующий origin на новый репозиторий?"):
                    run_git('remote', 'set-url', 'origin', repo_url)
                    print(f"{c.GREEN}✅ Remote origin обновлен{c.NC}")
                else:
                    print(f"{c.BLUE}ℹ️  Оставляем существующий remote origin{c.NC}")
                    repo_url = None
            else:
                run_git('remote', 'add', 'origin', repo_url)
                print(f"{c.GREEN}✅ Remote origin добавлен{c.NC}")

            # Ensure we're on main branch
            result = run_git('branch', '--show-current', capture=True)
            if result.stdout.strip() != 'main':
                run_git('branch', '-M', 'main')
                print(f"{c.GREEN}✅ Ветка переименована в main{c.NC}")

            # Push
            if repo_url:
                print(f"{c.YELLOW}🚀 Отправка в удаленный репозиторий...{c.NC}")
                result = run_git('push', '-u', 'origin', 'main', check=False)
                if result.returncode == 0:
                    print(f"{c.GREEN}✅ Проект успешно отправлен в удаленный репозиторий!{c.NC}")
                else:
                    print(f"{c.RED}❌ Ошибка при отправке в удаленный репозиторий{c.NC}")
                    print(f"{c.BLUE}🔧 Вы можете отправить позже: git push -u origin main{c.NC}")

    # ═══════════════════════════════════════════════════════════
    #                    CLEAN ARTIFACTS
    # ═══════════════════════════════════════════════════════════
    print(f"{c.BLUE}🧹 Очистка артефактов...{c.NC}")
    for pattern in ['.DS_Store', 'Thumbs.db', 'desktop.ini']:
        for f in Path('.').rglob(pattern):
            try:
                f.unlink()
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════
    #                   RENAME PROJECT FOLDER
    # ═══════════════════════════════════════════════════════════
    if rename_folder:
        print(f"{c.BLUE}📁 Переименование папки проекта...{c.NC}")
        parent_dir = Path.cwd().parent
        new_path = parent_dir / project_name

        if new_path.exists():
            print(f"{c.RED}❌ Папка '{project_name}' уже существует в родительской директории!{c.NC}")
            print(f"{c.YELLOW}💡 Попробуйте другое название проекта или переместите существующую папку{c.NC}")
        else:
            # This is tricky in Python - we'd need to rename after script exits
            print(f"{c.YELLOW}⚠️  Для переименования папки выполните после завершения скрипта:{c.NC}")
            print(f"   cd .. && mv {current_dir_name} {project_name} && cd {project_name}")

    # ═══════════════════════════════════════════════════════════
    #                     FINAL OUTPUT
    # ═══════════════════════════════════════════════════════════
    print()
    print(f"{c.GREEN}✅ Настройка завершена успешно!{c.NC}")
    print()
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print(f"{c.PURPLE}                    🎉 ГОТОВО К ЗАПУСКУ!                       {c.NC}")
    print(f"{c.PURPLE}═══════════════════════════════════════════════════════════════{c.NC}")
    print()
    print(f"{c.CYAN}📋 Следующие шаги:{c.NC}")
    print()

    step = 1
    if rename_folder:
        print(f"{c.YELLOW}{step}.{c.NC} Перейдите в папку проекта (если еще не там):")
        print(f"   {c.GREEN}cd {project_name}{c.NC}")
        print()
        step += 1

    print(f"{c.YELLOW}{step}.{c.NC} Запустите бота в режиме разработки:")
    print(f"   {c.GREEN}just dev-d{c.NC}  (или make dev-d)")
    print()
    step += 1

    print(f"{c.YELLOW}{step}.{c.NC} Проверьте статус сервисов:")
    print(f"   {c.GREEN}just status{c.NC}")
    print()
    step += 1

    print(f"{c.YELLOW}{step}.{c.NC} Посмотрите логи бота:")
    print(f"   {c.GREEN}just logs-bot{c.NC}")
    print()
    step += 1

    print(f"{c.YELLOW}{step}.{c.NC} Протестируйте бота в Telegram:")
    print(f"   Отправьте команды: {c.CYAN}/start{c.NC}, {c.CYAN}/help{c.NC}, {c.CYAN}/status{c.NC}")
    print()

    if not setup_remote_repo:
        print(f"{c.YELLOW}{step}.{c.NC} Подключите к удаленному репозиторию:")
        print(f"   {c.GREEN}git remote add origin YOUR_REPO_URL{c.NC}")
        print(f"   {c.GREEN}git push -u origin main{c.NC}")
        print()

    print(f"{c.BLUE}🔗 Полезные ссылки:{c.NC}")
    print(f"   • pgAdmin: {c.CYAN}http://localhost:{pgadmin_port}{c.NC} (admin@admin.com / admin)")
    print(f"   • PostgreSQL: {c.CYAN}localhost:{postgres_port}{c.NC}")
    print(f"   • Документация: {c.CYAN}README.md{c.NC}")
    if setup_remote_repo and repo_url:
        print(f"   • Репозиторий: {c.CYAN}{repo_url}{c.NC}")
    print()

    print(f"{c.YELLOW}🔐 Данные для подключения к БД:{c.NC}")
    print(f"   • База данных: {c.CYAN}{postgres_db}{c.NC}")
    print(f"   • Пользователь: {c.CYAN}{postgres_user}{c.NC}")
    print(f"   • Пароль: {c.CYAN}{postgres_password}{c.NC}")
    print(f"   {c.PURPLE}(сохраните пароль, он сгенерирован случайно!){c.NC}")
    print()

    print(f"{c.GREEN}🎯 Удачной разработки бота @{bot_username}! 🤖✨{c.NC}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
