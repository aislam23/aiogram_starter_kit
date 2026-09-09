#!/usr/bin/env python3
"""
Диагностика окружения: что готово, а что нет, до запуска бота.

Usage:
    python scripts/doctor.py            # человекочитаемый отчёт
    python scripts/doctor.py --json     # для агентов: {"ok": bool, "checks": [...]}
    python scripts/doctor.py --offline  # не ходить в Telegram за getMe

Секреты никогда не печатаются целиком. Код возврата 1, если провалена обязательная проверка.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,60}$")
TOKEN_PLACEHOLDERS = {"", "your_bot_token_here", "your_production_bot_token_here"}

Runner = Callable[[List[str]], Tuple[int, str]]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


# ── утилиты ──────────────────────────────────────────────────────

def parse_env(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def mask(token: str) -> str:
    return f"{token[:4]}…{token[-3:]}" if len(token) > 10 else "***"


def default_runner(cmd: List[str]) -> Tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return proc.returncode, (proc.stdout or proc.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


# ── отдельные проверки ───────────────────────────────────────────

def check_python() -> Check:
    ok = sys.version_info >= (3, 11)
    return Check("Python", ok, f"{sys.version.split()[0]}" + ("" if ok else " — нужен 3.11+"))


def check_command(binary: str, label: str, version_args: Optional[List[str]] = None,
                  runner: Runner = default_runner, required: bool = True) -> Check:
    if shutil.which(binary) is None:
        return Check(label, False, f"{binary} не найден в PATH", required)
    code, out = runner([binary] + (version_args or ["--version"]))
    return Check(label, code == 0, out.splitlines()[0] if out else "ok", required)


def check_docker_daemon(runner: Runner = default_runner) -> Check:
    if shutil.which("docker") is None:
        return Check("Docker daemon", False, "docker не установлен")
    code, out = runner(["docker", "info", "--format", "{{.ServerVersion}}"])
    return Check("Docker daemon", code == 0, f"server {out}" if code == 0 else "не запущен — откройте Docker Desktop")


def check_compose(runner: Runner = default_runner) -> Check:
    if shutil.which("docker") and runner(["docker", "compose", "version"])[0] == 0:
        return Check("Docker Compose", True, "docker compose (v2)")
    if shutil.which("docker-compose"):
        return Check("Docker Compose", True, "docker-compose (v1)")
    return Check("Docker Compose", False, "не найден")


def check_env_file(path: Path) -> Check:
    if path.exists():
        return Check(path.name, True, "найден")
    return Check(path.name, False, "нет файла — запустите: python scripts/init_project.py --name <имя> --admin-id <id>")


def check_token(env: Dict[str, str]) -> Check:
    token = env.get("BOT_TOKEN", "")
    if token in TOKEN_PLACEHOLDERS:
        return Check("BOT_TOKEN", False, "не задан — выполните: just set-token")
    if not TOKEN_RE.match(token):
        return Check("BOT_TOKEN", False, f"неверный формат ({mask(token)}) — выполните: just set-token")
    return Check("BOT_TOKEN", True, f"задан ({mask(token)})")


def check_token_online(env: Dict[str, str]) -> Check:
    import urllib.request

    token = env.get("BOT_TOKEN", "")
    if not TOKEN_RE.match(token):
        return Check("Telegram getMe", False, "токен не задан", required=False)
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=10) as resp:
            data = json.loads(resp.read().decode())
        username = data.get("result", {}).get("username")
        return Check("Telegram getMe", bool(username), f"@{username}" if username else "Telegram отверг токен", required=False)
    except Exception as e:
        return Check("Telegram getMe", False, f"нет ответа: {type(e).__name__}", required=False)


def check_admins(env: Dict[str, str]) -> Check:
    raw = env.get("ADMIN_USER_IDS", "").strip()
    ids = [x for x in re.findall(r"\d+", raw)]
    if not ids:
        return Check("ADMIN_USER_IDS", False, "нет ни одного ID администратора")
    return Check("ADMIN_USER_IDS", True, f"{len(ids)} админ(ов)")


def check_logs_dir(root: Path) -> Check:
    path = root / "logs"
    return Check("logs/", True, "есть" if path.exists() else "создастся при запуске", required=False)


# ── сборка отчёта ────────────────────────────────────────────────

def run_all(root: Path, online: bool = True, runner: Runner = default_runner) -> Dict:
    checks: List[Check] = [check_python()]
    checks.append(check_command("docker", "Docker CLI", runner=runner))
    checks.append(check_docker_daemon(runner))
    checks.append(check_compose(runner))
    checks.append(check_command("just", "just", runner=runner, required=False))

    env_path = root / ".env"
    checks.append(check_env_file(env_path))
    env = parse_env(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}
    checks.append(check_token(env))
    if online and env:
        checks.append(check_token_online(env))
    checks.append(check_admins(env))
    checks.append(check_logs_dir(root))

    ok = all(c.ok for c in checks if c.required)
    return {"ok": ok, "checks": [asdict(c) for c in checks]}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Проверка окружения перед запуском бота")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--offline", action="store_true", help="не проверять токен через Telegram")
    args = parser.parse_args(argv)

    report = run_all(Path(args.root).resolve(), online=not args.offline)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print("🩺 Проверка окружения\n")
        for c in report["checks"]:
            icon = "✅" if c["ok"] else ("❌" if c["required"] else "⚠️")
            print(f"  {icon} {c['name']:<16} {c['detail']}")
        print("\n" + ("✅ Всё готово, можно запускать: just dev-d" if report["ok"]
                      else "❌ Есть проблемы, см. выше"))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
