"""
Тесты серверного скрипта деплоя (scripts/deploy.py): автоопределение Docker Compose.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import deploy  # noqa: E402


def test_detect_compose_prefers_v2_plugin():
    runner = lambda cmd: (0, "Docker Compose version v2.29") if cmd[:3] == ["docker", "compose", "version"] else (1, "")  # noqa: E731
    assert deploy.detect_compose(runner) == ["docker", "compose"]


def test_detect_compose_falls_back_to_v1_binary():
    def runner(cmd):
        if cmd[:3] == ["docker", "compose", "version"]:
            return 1, ""
        if cmd[:2] == ["docker-compose", "--version"]:
            return 0, "docker-compose version 1.29"
        return 1, ""
    assert deploy.detect_compose(runner) == ["docker-compose"]


def test_detect_compose_returns_none_when_absent():
    assert deploy.detect_compose(lambda cmd: (1, "")) is None


def test_prod_compose_reads_interpolation_from_env_prod():
    # без --env-file compose берёт ${POSTGRES_PASSWORD} из .env, которого на сервере нет,
    # и пустое значение перебивает env_file: Postgres не стартует, Redis остаётся без пароля
    cmd = deploy.prod_compose(["docker", "compose"])
    assert cmd == ["docker", "compose", "--env-file", ".env.prod", "-f", "docker-compose.prod.yml"]


def test_every_prod_compose_call_passes_env_prod():
    # Makefile, shell-деплой и команды в документации должны вести себя так же, как deploy.py
    root = Path(__file__).resolve().parent.parent
    files = [root / "Makefile", root / "justfile", *(root / "scripts").glob("*.sh"), *(root / "docs").glob("*.md")]
    offenders = [
        f"{path.relative_to(root)}:{n}"
        for path in files
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "-f docker-compose.prod.yml" in line and "--env-file .env.prod" not in line
    ]
    assert offenders == []
