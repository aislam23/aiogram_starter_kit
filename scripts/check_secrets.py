#!/usr/bin/env python3
"""
Поиск секретов в коде перед коммитом: токены Telegram-ботов и захардкоженные пароли.

Usage:
    python scripts/check_secrets.py                 # все файлы под git (tracked + staged)
    python scripts/check_secrets.py --paths a.py b  # конкретные файлы

Найденные значения печатаются замаскированными. Код возврата 1, если что-то найдено.
Ложное срабатывание на заведомо тестовом значении: добавьте в строку `# noqa: secret`.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

TOKEN_RE = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,60}")
# Только присваивание через "=", чтобы не ловить аннотации типов (`secrets: list[str] = []`) и Makefile-цели
PASSWORD_ASSIGN_RE = re.compile(
    r"""(?i)\b[A-Z_]*(PASSWORD|SECRET|API_KEY|API_HASH)\s*=\s*["']?([A-Za-z0-9!@#$%^&*._\-+=/]{8,})["']?"""
)
PLACEHOLDER_HINTS = ("CHANGE_ME", "your_", "example", "placeholder", "<", "${", "os.environ", "Field(", "getenv",
                     "alias=", "securepassword", "re.compile")
DOC_SUFFIXES = {".md", ".example", ".txt"}  # в документации пароли-примеры допустимы, токены — нет
NOQA = "noqa: secret"
SKIP_NAMES = {".env", ".env.prod", ".env.local", ".env.staging", ".env.test"}
SKIP_DIRS = {".venv", "venv", "node_modules", ".git", "__pycache__", "logs", ".deploy"}
TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".md", ".txt", ".toml", ".json", ".sh", ".env", "", ".example", ".cfg", ".ini", ".sql"}


@dataclass
class Hit:
    line: int
    kind: str
    masked: str


@dataclass
class Finding:
    path: Path
    hit: Hit


def _mask(value: str) -> str:
    return f"{value[:4]}…{value[-3:]}" if len(value) > 10 else "***"


def find_secrets(text: str, check_passwords: bool = True) -> List[Hit]:
    hits: List[Hit] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if NOQA in line:
            continue
        for match in TOKEN_RE.finditer(line):
            hits.append(Hit(number, "telegram bot token", _mask(match.group(0))))
        if not check_passwords:
            continue
        for match in PASSWORD_ASSIGN_RE.finditer(line):
            value = match.group(2)
            if value.startswith("$") or value.startswith("%"):
                continue  # подстановка переменной ($VAR, ${VAR}, %VAR%), а не значение
            if any(hint.lower() in line.lower() for hint in PLACEHOLDER_HINTS):
                continue
            if TOKEN_RE.fullmatch(value):
                continue  # уже учтён выше
            hits.append(Hit(number, "hardcoded password/secret", _mask(value)))
    return hits


def _should_skip(path: Path) -> bool:
    if path.name in SKIP_NAMES or any(part in SKIP_DIRS for part in path.parts):
        return True
    return path.suffix not in TEXT_SUFFIXES and not path.name.startswith(".env")


def scan_paths(paths: Iterable[Path]) -> List[Finding]:
    findings: List[Finding] = []
    for path in paths:
        if not path.is_file() or _should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        check_passwords = path.suffix not in DOC_SUFFIXES and not path.name.endswith(".example")
        findings.extend(Finding(path, hit) for hit in find_secrets(text, check_passwords=check_passwords))
    return findings


def git_files(root: Path) -> List[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                             cwd=root, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in root.rglob("*") if p.is_file()]
    return [root / line for line in out.splitlines() if line.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Поиск секретов в файлах проекта")
    parser.add_argument("--paths", nargs="*", help="файлы для проверки (по умолчанию — все под git)")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    paths = [Path(p) for p in args.paths] if args.paths else git_files(root)
    findings = scan_paths(paths)

    if not findings:
        print("✅ Секретов в коде не найдено")
        return 0
    print(f"❌ Найдено {len(findings)} возможных секрет(ов):")
    for f in findings:
        try:
            shown = f.path.relative_to(root)
        except ValueError:
            shown = f.path
        print(f"   {shown}:{f.hit.line}  {f.hit.kind}  ({f.hit.masked})")
    print("\nУберите значение в .env или пометьте строку `# noqa: secret`, если это тестовое значение.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
