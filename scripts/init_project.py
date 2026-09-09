#!/usr/bin/env python3
"""
Инициализация нового проекта из шаблона. Без диалогов, идемпотентно, без git-операций.

Usage:
    python scripts/init_project.py --name my_bot --admin @artem        # админ по username (ID узнает бот)
    python scripts/init_project.py --name my_bot --admin 123456789     # или по Telegram ID
    python scripts/init_project.py --name my_bot --admin @artem --description "Бот для заметок" --author "Имя"
    python scripts/init_project.py --name my_bot --admin @artem --postgres-port 5433 --json

Что делает:
- создаёт .env и .env.prod из примеров, генерирует пароли (существующие значения не трогает);
- переименовывает Docker-контейнеры и volumes под имя проекта;
- меняет порты, если указаны;
- обновляет app/__init__.py и заголовок README.md.

Чего НЕ делает (сознательно): не читает токен, не трогает git, не переименовывает папку,
не создаёт репозиторий на GitHub. Токен ставится отдельно: `just set-token`.

Если обязательные аргументы не переданы и скрипт запущен в терминале человеком,
он спросит их обычным видимым вводом. Без терминала — завершится с кодом 2 и подсказкой.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import string
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

TEMPLATE_NAME = "aiogram_starter_kit"
CONTAINER_PREFIX = "aiogram"
TOKEN_PLACEHOLDERS = {"", "your_bot_token_here", "your_production_bot_token_here"}


USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{3,31}$")


def parse_admin(raw: str) -> tuple[Optional[int], Optional[str]]:
    """'123456' → (123456, None); '@Artem' / 'https://t.me/Artem' → (None, 'artem')."""
    value = raw.strip()
    if value.isdigit():
        return int(value), None
    value = re.sub(r"^(https?://)?(t\.me|telegram\.me)/", "", value, flags=re.IGNORECASE).lstrip("@").lower()
    if USERNAME_RE.match(value):
        return None, value
    raise ValueError(f"'{raw}' не похоже ни на Telegram ID, ни на username")


@dataclass
class ProjectConfig:
    name: str
    admin_id: Optional[int] = None
    admin_username: Optional[str] = None
    description: str = "Telegram бот на Aiogram"
    author: str = "Your Name"
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    postgres_port: Optional[int] = None
    pgadmin_port: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.admin_id and not self.admin_username:
            raise ValueError("Нужен admin_id или admin_username")
        if self.admin_username:
            self.admin_username = parse_admin(self.admin_username)[1]
        self.name = slugify(self.name)
        self.db_name = self.db_name or f"{self.name}_db"
        self.db_user = self.db_user or f"{self.name}_user"


# ── чистые функции ───────────────────────────────────────────────

def slugify(name: str) -> str:
    """Безопасное имя для Docker, БД и переменных: только [a-z0-9_]."""
    slug = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")
    return re.sub(r"_+", "_", slug) or "my_telegram_bot"


def generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def parse_env(text: str) -> Dict[str, str]:
    """Прочитать KEY=VALUE строки (комментарии и пустые строки пропускаются)."""
    result: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def update_env_text(text: str, updates: Dict[str, str]) -> str:
    """Заменить значения ключей в тексте .env, сохранив комментарии; недостающие ключи дописать."""
    lines = text.splitlines()
    seen = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            lines[i] = f"{key}={updates[key]}"
            seen.add(key)
    missing = [k for k in updates if k not in seen]
    if missing:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(f"{k}={updates[k]}" for k in missing)
    return "\n".join(lines) + "\n"


def replace_in_file(path: Path, replacements: List[tuple[str, str]]) -> bool:
    """Применить замены к файлу. Возвращает True, если файл изменился."""
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8")
    content = original
    for old, new in replacements:
        content = content.replace(old, new)
    if content != original:
        path.write_text(content, encoding="utf-8")
        return True
    return False


# ── применение ───────────────────────────────────────────────────

def _render_env(root: Path, target: str, example: str, values: Dict[str, str], keep: List[str]) -> Path:
    """Создать/обновить env-файл: существующие значения из `keep` и уже заданные пароли сохраняются."""
    target_path, example_path = root / target, root / example
    base_text = target_path.read_text(encoding="utf-8") if target_path.exists() else (
        example_path.read_text(encoding="utf-8") if example_path.exists() else ""
    )
    existing = parse_env(base_text)

    final = dict(values)
    for key in keep:
        if key in existing and existing[key] not in TOKEN_PLACEHOLDERS:
            final[key] = existing[key]
    # уже сгенерированные пароли не перегенерируем — иначе сломается существующая база
    for key in ("POSTGRES_PASSWORD", "REDIS_PASSWORD"):
        current = existing.get(key, "")
        if key in final and current and "CHANGE_ME" not in current and current != "securepassword":
            final[key] = current

    target_path.write_text(update_env_text(base_text, final), encoding="utf-8")
    try:
        target_path.chmod(0o600)
    except OSError:
        pass
    return target_path


def apply(root: Path, cfg: ProjectConfig) -> Dict[str, List[str]]:
    """Применить конфигурацию к проекту в `root`. Возвращает списки записанных/изменённых файлов."""
    written: List[str] = []
    changed: List[str] = []

    # .env (разработка)
    admin_ids = f"[{cfg.admin_id}]" if cfg.admin_id else "[]"
    admin_usernames = json.dumps([cfg.admin_username]) if cfg.admin_username else "[]"
    dev_values = {
        "ADMIN_USER_IDS": admin_ids,
        "ADMIN_USERNAMES": admin_usernames,
        "POSTGRES_DB": cfg.db_name,
        "POSTGRES_USER": cfg.db_user,
        "POSTGRES_PASSWORD": generate_password(24),
        "ENV": "development",
        "EXAMPLE_HANDLERS": "true",
    }
    _render_env(root, ".env", ".env.example", dev_values, keep=["BOT_TOKEN", "BOT_USERNAME"])
    written.append(".env")

    # .env.prod — токен берём из .env, если он там уже есть
    dev_env = parse_env((root / ".env").read_text(encoding="utf-8"))
    prod_values = {
        "ADMIN_USER_IDS": admin_ids,
        "ADMIN_USERNAMES": admin_usernames,
        "POSTGRES_DB": f"{cfg.db_name}_prod",
        "POSTGRES_USER": f"{cfg.db_user}_prod",
        "POSTGRES_PASSWORD": generate_password(32),
        "REDIS_PASSWORD": generate_password(32),
        "ENV": "production",
        "LOG_LEVEL": "WARNING",
        "EXAMPLE_HANDLERS": "false",
    }
    if dev_env.get("BOT_TOKEN") not in TOKEN_PLACEHOLDERS:
        prod_values["BOT_TOKEN"] = dev_env["BOT_TOKEN"]
        prod_values["BOT_USERNAME"] = dev_env.get("BOT_USERNAME", "")
    _render_env(root, ".env.prod", ".env.prod.example", prod_values, keep=["BOT_TOKEN", "BOT_USERNAME"])
    written.append(".env.prod")

    # Docker: имена контейнеров, volumes, порты
    compose, compose_prod = root / "docker-compose.yml", root / "docker-compose.prod.yml"
    name_replacements = [(f"container_name: {CONTAINER_PREFIX}_", f"container_name: {cfg.name}_"),
                         (f"{TEMPLATE_NAME}_", f"{cfg.name}_")]
    if replace_in_file(compose, name_replacements):
        changed.append("docker-compose.yml")
    if replace_in_file(compose_prod, name_replacements):
        changed.append("docker-compose.prod.yml")

    port_replacements = []
    if cfg.postgres_port:
        port_replacements.append((re.compile(r'"\d+:5432"'), f'"{cfg.postgres_port}:5432"'))
    if cfg.pgadmin_port:
        port_replacements.append((re.compile(r'"\d+:80"'), f'"{cfg.pgadmin_port}:80"'))
    if port_replacements and compose.exists():
        text = original = compose.read_text(encoding="utf-8")
        for pattern, new in port_replacements:
            text = pattern.sub(new, text)
        if text != original:
            compose.write_text(text, encoding="utf-8")
            if "docker-compose.yml" not in changed:
                changed.append("docker-compose.yml")

    # justfile / Makefile: имя проекта
    if replace_in_file(root / "justfile", [(f'project_name := "{TEMPLATE_NAME}"', f'project_name := "{cfg.name}"')]):
        changed.append("justfile")
    if replace_in_file(root / "Makefile", [(f"PROJECT_NAME = {TEMPLATE_NAME}", f"PROJECT_NAME = {cfg.name}")]):
        changed.append("Makefile")

    # Метаданные приложения
    app_init = root / "app" / "__init__.py"
    if app_init.exists():
        new_init = f'"""\n{cfg.description}\n"""\n\n__version__ = "1.0.0"\n__author__ = "{cfg.author}"\n'
        if app_init.read_text(encoding="utf-8") != new_init:
            app_init.write_text(new_init, encoding="utf-8")
            changed.append("app/__init__.py")

    # README: заголовок
    readme = root / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        new_text = re.sub(r"^# 🤖 .*$", f"# 🤖 {cfg.name}", text, count=1, flags=re.MULTILINE)
        if new_text != text:
            readme.write_text(new_text, encoding="utf-8")
            changed.append("README.md")

    return {"written": written, "changed": changed}


# ── CLI ──────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Инициализация проекта из шаблона (без диалогов)")
    p.add_argument("--name", help="имя проекта: [a-z0-9_], используется для Docker и БД")
    p.add_argument("--admin", help="администратор: Telegram ID или @username (бот сам узнает ID при первом сообщении)")
    p.add_argument("--admin-id", type=int, help="Telegram ID администратора (то же, что --admin <id>)")
    p.add_argument("--description", default="Telegram бот на Aiogram")
    p.add_argument("--author", default="Your Name")
    p.add_argument("--db-name")
    p.add_argument("--db-user")
    p.add_argument("--postgres-port", type=int, help="внешний порт PostgreSQL (по умолчанию 5432)")
    p.add_argument("--pgadmin-port", type=int, help="внешний порт pgAdmin (по умолчанию 8080)")
    p.add_argument("--root", default=".", help="корень проекта")
    p.add_argument("--json", action="store_true", help="машиночитаемый отчёт")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    if not (root / "docker-compose.yml").exists() or not (root / ".env.example").exists():
        print(f"❌ {root} не похож на корень aiogram_starter_kit (нет docker-compose.yml / .env.example)", file=sys.stderr)
        return 2

    name = args.name
    admin_id, admin_username = args.admin_id, None
    if args.admin:
        try:
            admin_id, admin_username = parse_admin(args.admin)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 2
    if (not name or not (admin_id or admin_username)) and sys.stdin.isatty() and not args.json:
        print("🚀 Настройка нового проекта (значения видны при вводе — это нормально, здесь нет секретов)\n")
        name = name or _ask("Имя проекта (латиница, без пробелов)", "my_telegram_bot")
        while not (admin_id or admin_username):
            try:
                admin_id, admin_username = parse_admin(_ask("Ваш username в Telegram (например @artem) или ID"))
            except ValueError as e:
                print(f"   {e}")
    if not name or not (admin_id or admin_username):
        print("❌ Нужны аргументы --name и --admin.\n"
              "   Пример: python scripts/init_project.py --name my_bot --admin @artem", file=sys.stderr)
        return 2

    cfg = ProjectConfig(
        name=name, admin_id=admin_id, admin_username=admin_username,
        description=args.description, author=args.author,
        db_name=args.db_name, db_user=args.db_user,
        postgres_port=args.postgres_port, pgadmin_port=args.pgadmin_port,
    )
    result = apply(root, cfg)
    next_steps = [
        "just set-token        # безопасно записать токен от @BotFather (без ввода в чат)",
        "just doctor           # проверить окружение",
        "just check            # линтер и тесты без Docker",
        "just dev-d            # запустить бота",
    ]

    if args.json:
        print(json.dumps({"ok": True, "project": cfg.name, **result, "next_steps": next_steps}, ensure_ascii=False))
        return 0

    print(f"✅ Проект «{cfg.name}» настроен")
    print(f"   Записано: {', '.join(result['written'])}")
    if result["changed"]:
        print(f"   Изменено: {', '.join(result['changed'])}")
    print("\nСледующие шаги:")
    for step in next_steps:
        print(f"   {step}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
