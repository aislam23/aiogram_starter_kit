#!/usr/bin/env python3
"""
Публикация секретов деплоя в GitHub Actions через `gh` CLI — без копирования значений вручную.

Берёт данные из .deploy/server.json, ключ из .deploy/deploy_key и содержимое .env.prod,
и записывает их в секреты репозитория (origin): SERVER_HOST, SERVER_PORT, SERVER_USER,
SSH_PRIVATE_KEY, PROJECT_PATH, ENV_PROD. Значения передаются gh через stdin и в stdout не попадают.

Usage:
    python scripts/github_secrets.py
Требуется: gh (https://cli.github.com), `gh auth login`, remote origin на GitHub.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import server_config as sc

Runner = Callable[[List[str], Optional[str]], Tuple[int, str]]
SECRET_ORDER = ["SERVER_HOST", "SERVER_PORT", "SERVER_USER", "SSH_PRIVATE_KEY", "PROJECT_PATH", "ENV_PROD"]


def default_runner(cmd: List[str], input_text: Optional[str] = None) -> Tuple[int, str]:
    try:
        proc = subprocess.run(cmd, input=input_text, capture_output=True, text=True, timeout=60)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def collect_secrets(root: Path, cfg: sc.ServerConfig) -> Dict[str, str]:
    return {
        "SERVER_HOST": cfg.host,
        "SERVER_PORT": str(cfg.port),
        "SERVER_USER": cfg.user,
        "SSH_PRIVATE_KEY": cfg.key_path(root).read_text(encoding="utf-8"),
        "PROJECT_PATH": cfg.project_path,
        "ENV_PROD": (root / ".env.prod").read_text(encoding="utf-8"),
    }


def check_gh(runner: Runner = default_runner) -> List[str]:
    """Список проблем (пустой — всё готово)."""
    problems = []
    if runner(["gh", "--version"], None)[0] != 0:
        problems.append("gh не установлен: https://cli.github.com (macOS: brew install gh, Windows: winget install GitHub.cli)")
    elif runner(["gh", "auth", "status"], None)[0] != 0:
        problems.append("gh не авторизован: выполните в терминале `gh auth login` (откроется браузер)")
    if runner(["git", "remote", "get-url", "origin"], None)[0] != 0:
        problems.append("нет remote origin: создайте репозиторий на GitHub и выполните `gh repo create` или `git remote add origin …`")
    return problems


def publish(secrets: Dict[str, str], runner: Runner = default_runner) -> List[str]:
    """Записать секреты по одному. Значение идёт в stdin, а не в аргументы (не видно в списке процессов)."""
    done = []
    for name in SECRET_ORDER:
        code, out = runner(["gh", "secret", "set", name], secrets[name])
        if code != 0:
            raise RuntimeError(f"gh secret set {name}: {out[:200]}")
        done.append(name)
    return done


def main(argv: Optional[List[str]] = None, runner: Runner = default_runner) -> int:
    parser = argparse.ArgumentParser(description="Опубликовать секреты деплоя в GitHub Actions")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    cfg = sc.load(root)
    if cfg is None:
        print("❌ Сервер не настроен. Сначала: just set-server")
        return 1
    if not (root / ".env.prod").exists():
        print("❌ Нет .env.prod. Сначала: just init <имя> @username и just set-token")
        return 1

    problems = check_gh(runner)
    if problems:
        print("❌ GitHub CLI не готов:")
        for p in problems:
            print(f"   • {p}")
        return 1

    try:
        names = publish(collect_secrets(root, cfg), runner)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    print(f"✅ Секреты для {cfg.describe()} записаны в GitHub: {', '.join(names)}")
    print("   Теперь каждый push в main деплоит бота. Проверить: вкладка Actions в репозитории.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
