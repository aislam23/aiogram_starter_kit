"""
Тесты логирования: секреты маскируются, файл пишется в формате JSON Lines.
"""
import json

from loguru import logger

from app.utils.logging import mask_secrets, setup_logging

TOKEN = "123456789:AAHfiqksKZ8WmR2zSjiQ7_v4TMAKdiHm9T0"  # noqa: secret — тестовое значение


def test_mask_secrets_hides_bot_token_in_text():
    masked = mask_secrets(f"request to https://api.telegram.org/bot{TOKEN}/getMe failed")
    assert TOKEN not in masked
    assert "AAHfiqksKZ8WmR2zSjiQ7" not in masked
    assert "getMe failed" in masked


def test_mask_secrets_leaves_ordinary_text_untouched():
    text = "📥 Message from 123456 (@tester): '/start'"
    assert mask_secrets(text) == text


def test_mask_secrets_hides_explicitly_known_secret():
    masked = mask_secrets("password is hunter2hunter2", extra_secrets=["hunter2hunter2"])
    assert "hunter2hunter2" not in masked


def test_setup_logging_writes_masked_jsonl(tmp_path):
    log_file = tmp_path / "bot.jsonl"
    setup_logging(level="INFO", log_file=str(log_file), colorize=False)
    try:
        logger.info(f"bot token is {TOKEN}")
        logger.complete()
    finally:
        logger.remove()

    lines = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    record = lines[0]["record"]
    assert record["level"]["name"] == "INFO"
    assert TOKEN not in record["message"]
    assert "bot token is" in record["message"]


def test_setup_logging_without_file_only_uses_stdout(tmp_path):
    setup_logging(level="INFO", log_file="", colorize=False)
    try:
        logger.info("hello")
    finally:
        logger.remove()
    assert list(tmp_path.iterdir()) == []
