"""
Настройка логирования.

- В stdout: человекочитаемый формат (для `just logs-bot`).
- В файл (LOG_FILE, по умолчанию logs/bot.jsonl): JSON Lines, чтобы агент мог
  прочитать логи программно и понять, что бот запустился и что ответил.
- Во всех сообщениях маскируются токены Telegram и известные секреты.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, Optional

from loguru import logger

TOKEN_RE = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,60}")

_known_secrets: list[str] = []


def _mask(value: str) -> str:
    return f"{value[:4]}…{value[-3:]}" if len(value) > 10 else "***"


def mask_secrets(text: str, extra_secrets: Optional[Iterable[str]] = None) -> str:
    """Скрыть токены ботов и явно переданные секреты в произвольном тексте."""
    if not text:
        return text
    result = TOKEN_RE.sub(lambda m: _mask(m.group(0)), text)
    for secret in list(extra_secrets or []) + _known_secrets:
        if secret and secret in result:
            result = result.replace(secret, _mask(secret))
    return result


def register_secret(value: str) -> None:
    """Добавить значение, которое нужно маскировать во всех логах (пароль БД и т.п.)."""
    if value and value not in _known_secrets:
        _known_secrets.append(value)


def _patcher(record) -> None:
    record["message"] = mask_secrets(record["message"])


STDOUT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None, colorize: bool = True) -> None:
    """Сконфигурировать loguru: stdout + (опционально) JSON-файл с ротацией."""
    logger.remove()
    logger.configure(patcher=_patcher)
    logger.add(sys.stdout, level=level, format=STDOUT_FORMAT, colorize=colorize)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(path),
            level=level,
            serialize=True,
            rotation="10 MB",
            retention=5,
            enqueue=False,
            encoding="utf-8",
        )
