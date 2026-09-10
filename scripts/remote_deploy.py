#!/usr/bin/env python3
"""
Деплой бота на сервер по SSH прямо с этой машины (или с раннера GitHub Actions).

Что делает `deploy`:
1. Подключается по ключу из .deploy/ (после `just set-server`) или по данным из флагов/переменных окружения (CI).
2. Ставит Docker на сервере, если его нет.
3. Загружает файлы проекта (то, что под git; без .env, .deploy, .git, .venv, logs) и .env.prod.
4. Запускает на сервере `python3 scripts/deploy.py --ci` — тот же скрипт, что и при ручном деплое.

Usage:
    python scripts/remote_deploy.py deploy
    python scripts/remote_deploy.py logs [N]
    python scripts/remote_deploy.py status
    python scripts/remote_deploy.py deploy --host 1.2.3.4 --user root --key-file /tmp/key --project-path /root/bot

Переменные окружения для CI: SERVER_HOST, SERVER_PORT, SERVER_USER, SSH_KEY_FILE, PROJECT_PATH.
В stdout адрес сервера только под маской.
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import server_config as sc

Runner = Callable[[List[str], Path], Tuple[int, str]]
Connect = Callable[[sc.Credentials], sc.SshSession]

EXCLUDED_DIRS = {".git", ".venv", "venv", ".deploy", "logs", "__pycache__", ".pytest_cache", ".ruff_cache",
                 "node_modules", ".idea", ".vscode"}
COMPOSE_PROD = "docker compose -f docker-compose.prod.yml"


def default_runner(cmd: List[str], cwd: Path) -> Tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


# ── что загружать ────────────────────────────────────────────────

def _is_secret_or_junk(rel: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return True
    name = rel.name
    if name.startswith(".env") and not name.endswith(".example"):
        return True
    return name in {".DS_Store", "Thumbs.db"}


def project_files(root: Path, runner: Runner = default_runner) -> List[Path]:
    """Файлы проекта относительно root: из git (tracked + untracked, без ignored), иначе обход папки."""
    code, out = runner(["git", "ls-files", "--cached", "--others", "--exclude-standard"], root)
    if code == 0:
        candidates = [Path(line) for line in out.splitlines() if line.strip()]
    else:
        candidates = [p.relative_to(root) for p in root.rglob("*") if p.is_file()]
    return sorted(p for p in candidates if not _is_secret_or_junk(p) and (root / p).is_file())


def build_tarball(root: Path, files: List[Path]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for rel in files:
            tar.add(root / rel, arcname=rel.as_posix())
    return buffer.getvalue()


# ── команды на сервере ───────────────────────────────────────────

def ensure_docker_script() -> str:
    return (
        "if ! command -v docker >/dev/null 2>&1; then "
        "echo '=== Устанавливаю Docker (1-3 минуты) ==='; "
        "curl -fsSL https://get.docker.com | sh; "
        "fi; "
        "docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || "
        "(echo 'Docker Compose не найден' && exit 1); "
        "command -v python3 >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq python3)"
    )


def deploy_script(project_path: str, archive_path: str) -> str:
    return (
        f"mkdir -p {project_path} && cd {project_path} && "
        f"tar -xzf {archive_path} && rm -f {archive_path} && "
        "mkdir -p logs && python3 scripts/deploy.py --ci"
    )


def _compose_in(project_path: str, tail: str) -> str:
    return (
        f"cd {project_path} && "
        f"(docker compose version >/dev/null 2>&1 && docker compose -f docker-compose.prod.yml {tail} "
        f"|| docker-compose -f docker-compose.prod.yml {tail})"
    )


# ── сценарии ─────────────────────────────────────────────────────

def _creds(root: Path, cfg: sc.ServerConfig) -> sc.Credentials:
    return sc.Credentials(host=cfg.host, port=cfg.port, user=cfg.user, key_file=str(cfg.key_path(root)))


def deploy(root: Path, cfg: sc.ServerConfig, connect: Connect = sc.connect, runner: Runner = default_runner) -> int:
    env_prod = root / ".env.prod"
    if not env_prod.exists():
        print("❌ Нет .env.prod. Создайте его: just init <имя> @username, затем just set-token")
        return 1

    files = project_files(root, runner)
    archive = build_tarball(root, files)
    archive_path = f"/tmp/{root.name}.tar.gz"
    print(f"🚀 Деплой на {cfg.describe()} → {cfg.project_path} ({len(files)} файлов)")

    try:
        with connect(_creds(root, cfg)) as session:
            print("🐳 Проверяю Docker на сервере…")
            code, out = session.run(ensure_docker_script(), stream=True)
            if code != 0:
                print("❌ Не удалось подготовить Docker на сервере")
                return 1
            print("📦 Загружаю проект и настройки…")
            session.upload_bytes(archive, archive_path, mode=0o600)
            session.run(f"mkdir -p {cfg.project_path}")
            session.upload_bytes(env_prod.read_bytes(), f"{cfg.project_path}/.env.prod", mode=0o600)
            print("🏭 Запускаю бота на сервере…")
            code, out = session.run(deploy_script(cfg.project_path, archive_path), stream=True)
    except sc.SshError as e:
        print(f"❌ {e}")
        return 1

    if code != 0:
        print("❌ Деплой завершился с ошибкой. Логи: just server-logs 50")
        return code
    print(f"✅ Бот задеплоен на {cfg.describe()}. Логи: just server-logs, статус: just server-status")
    return 0


def logs(cfg: sc.ServerConfig, n: int = 50, connect: Connect = sc.connect, root: Optional[Path] = None) -> int:
    with connect(_creds(root or Path("."), cfg)) as session:
        code, _ = session.run(_compose_in(cfg.project_path, f"logs --tail={n} bot"), stream=True)
    return code


def status(cfg: sc.ServerConfig, connect: Connect = sc.connect, root: Optional[Path] = None) -> int:
    with connect(_creds(root or Path("."), cfg)) as session:
        code, _ = session.run(_compose_in(cfg.project_path, "ps"), stream=True)
    return code


# ── источник настроек ────────────────────────────────────────────

def resolve_config(root: Path, host: str = "", port: str = "", user: str = "", key_file: str = "",
                   project_path: str = "") -> Optional[sc.ServerConfig]:
    """Флаги/переменные окружения (CI) важнее .deploy/server.json."""
    if host:
        user = user or "root"
        return sc.ServerConfig(
            host=host.strip(), port=sc.parse_port(port), user=user,
            key_file=key_file or sc.KEY_NAME, project_path=project_path or sc.default_project_path(user, root.name),
        )
    return sc.load(root)


def main(argv: Optional[List[str]] = None, connect: Connect = sc.connect) -> int:
    parser = argparse.ArgumentParser(description="Деплой на сервер по SSH")
    parser.add_argument("action", choices=["deploy", "logs", "status"])
    parser.add_argument("n", nargs="?", default="50", help="строк логов")
    parser.add_argument("--root", default=".")
    parser.add_argument("--host", default=os.environ.get("SERVER_HOST", ""))
    parser.add_argument("--port", default=os.environ.get("SERVER_PORT", ""))
    parser.add_argument("--user", default=os.environ.get("SERVER_USER", ""))
    parser.add_argument("--key-file", default=os.environ.get("SSH_KEY_FILE", ""))
    parser.add_argument("--project-path", default=os.environ.get("PROJECT_PATH", ""))
    args = parser.parse_args(argv)

    missing = sc.missing_ssh_deps()
    if missing:
        print(f"❌ {missing}")
        return 1
    root = Path(args.root).resolve()
    try:
        cfg = resolve_config(root, args.host, args.port, args.user, args.key_file, args.project_path)
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    if cfg is None:
        print("❌ Сервер не настроен. Сначала: just set-server")
        return 1

    try:
        if args.action == "deploy":
            return deploy(root, cfg, connect)
        if args.action == "logs":
            return logs(cfg, int(args.n), connect, root)
        return status(cfg, connect, root)
    except sc.SshError as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
