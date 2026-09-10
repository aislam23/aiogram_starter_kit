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
