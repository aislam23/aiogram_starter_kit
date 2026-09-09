"""
Тесты для scripts/set_token.py — безопасный ввод BOT_TOKEN без участия агента.
"""
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import set_token  # noqa: E402

VALID_TOKEN = "123456789:AAHfiqksKZ8WmR2zSjiQ7_v4TMAKdiHm9T0"  # noqa: secret — тестовое значение


# ── формат токена ────────────────────────────────────────────────

def test_looks_like_token_accepts_real_format():
    assert set_token.looks_like_token(VALID_TOKEN)


@pytest.mark.parametrize("junk", [
    "",
    "hello world",
    "my password 123",
    "123456789",
    "123456789:short",
    "abc:AAHfiqksKZ8WmR2zSjiQ7_v4TMAKdiHm9T0",
    "https://t.me/some_bot",
])
def test_looks_like_token_rejects_junk(junk):
    assert not set_token.looks_like_token(junk)


def test_looks_like_token_tolerates_surrounding_whitespace():
    assert set_token.looks_like_token(f"  {VALID_TOKEN}\n")


# ── маскирование ─────────────────────────────────────────────────

def test_mask_hides_middle_of_token():
    masked = set_token.mask(VALID_TOKEN)
    assert masked.startswith("1234")
    assert masked.endswith("9T0")
    assert "AAHfiqksKZ8WmR2zSjiQ7" not in masked
    assert len(masked) < len(VALID_TOKEN)


# ── запись в .env ────────────────────────────────────────────────

def test_write_env_replaces_existing_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BOT_TOKEN=old\nBOT_USERNAME=old_bot\nLOG_LEVEL=INFO\n")

    set_token.write_env(env, tmp_path / ".env.example", VALID_TOKEN, "new_bot")

    lines = env.read_text().splitlines()
    assert f"BOT_TOKEN={VALID_TOKEN}" in lines
    assert "BOT_USERNAME=new_bot" in lines
    assert "LOG_LEVEL=INFO" in lines
    assert "BOT_TOKEN=old" not in lines


def test_write_env_creates_file_from_example_when_missing(tmp_path):
    example = tmp_path / ".env.example"
    example.write_text("BOT_TOKEN=your_bot_token_here\nBOT_USERNAME=x\nREDIS_DB=0\n")
    env = tmp_path / ".env"

    set_token.write_env(env, example, VALID_TOKEN, "new_bot")

    lines = env.read_text().splitlines()
    assert f"BOT_TOKEN={VALID_TOKEN}" in lines
    assert "BOT_USERNAME=new_bot" in lines
    assert "REDIS_DB=0" in lines


def test_write_env_appends_keys_when_absent(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LOG_LEVEL=INFO\n")

    set_token.write_env(env, tmp_path / ".env.example", VALID_TOKEN, "new_bot")

    lines = env.read_text().splitlines()
    assert f"BOT_TOKEN={VALID_TOKEN}" in lines
    assert "BOT_USERNAME=new_bot" in lines


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
def test_write_env_restricts_permissions_to_owner(tmp_path):
    env = tmp_path / ".env"
    set_token.write_env(env, tmp_path / ".env.example", VALID_TOKEN, "new_bot")
    assert env.stat().st_mode & 0o777 == 0o600


# ── буфер обмена ─────────────────────────────────────────────────

def test_token_from_clipboard_returns_verified_token():
    result = set_token.token_from_clipboard(
        read_clipboard=lambda: VALID_TOKEN,
        verify=lambda t: "some_bot" if t == VALID_TOKEN else None,
    )
    assert result == (VALID_TOKEN, "some_bot")


def test_token_from_clipboard_ignores_junk_without_calling_verify():
    calls = []

    def verify(t):
        calls.append(t)
        return "some_bot"

    result = set_token.token_from_clipboard(
        read_clipboard=lambda: "my secret password",
        verify=verify,
    )
    assert result is None
    assert calls == []


def test_token_from_clipboard_returns_none_when_telegram_rejects():
    result = set_token.token_from_clipboard(
        read_clipboard=lambda: VALID_TOKEN,
        verify=lambda t: None,
    )
    assert result is None


def test_token_from_clipboard_survives_missing_clipboard_tool():
    def broken():
        raise FileNotFoundError("xclip not found")

    assert set_token.token_from_clipboard(read_clipboard=broken, verify=lambda t: "x") is None


# ── страница в браузере ──────────────────────────────────────────

def _post(url: str, data: dict) -> str:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read().decode()


def test_form_server_accepts_valid_token_and_stops():
    server = set_token.TokenFormServer(verify=lambda t: "form_bot" if t == VALID_TOKEN else None)
    thread = threading.Thread(target=server.serve_until_token, kwargs={"timeout": 5})
    thread.start()

    page = urllib.request.urlopen(server.url, timeout=5).read().decode()
    assert "<form" in page

    response = _post(server.url, {"token": VALID_TOKEN})
    thread.join(timeout=5)

    assert "@form_bot" in response
    assert server.result == (VALID_TOKEN, "form_bot")
    assert not thread.is_alive()


def test_form_server_rejects_bad_token_and_keeps_waiting():
    server = set_token.TokenFormServer(verify=lambda t: None)
    thread = threading.Thread(target=server.serve_until_token, kwargs={"timeout": 5})
    thread.start()

    response = _post(server.url, {"token": "not a token"})
    assert "<form" in response
    assert server.result is None
    assert thread.is_alive()

    server.shutdown()
    thread.join(timeout=5)


def test_form_server_times_out_without_token():
    server = set_token.TokenFormServer(verify=lambda t: "x")
    server.serve_until_token(timeout=0.3)
    assert server.result is None


# ── общий сценарий ───────────────────────────────────────────────

def test_obtain_token_prefers_clipboard():
    form_calls = []

    result = set_token.obtain_token(
        read_clipboard=lambda: VALID_TOKEN,
        verify=lambda t: "clip_bot",
        run_form=lambda: form_calls.append(1) or (VALID_TOKEN, "form_bot"),
    )
    assert result == (VALID_TOKEN, "clip_bot")
    assert form_calls == []


def test_obtain_token_falls_back_to_form():
    result = set_token.obtain_token(
        read_clipboard=lambda: "junk",
        verify=lambda t: "x",
        run_form=lambda: (VALID_TOKEN, "form_bot"),
    )
    assert result == (VALID_TOKEN, "form_bot")


# ── целевые файлы ────────────────────────────────────────────────

def test_target_env_files_includes_prod_when_it_exists(tmp_path):
    (tmp_path / ".env").write_text("BOT_TOKEN=x\n")
    (tmp_path / ".env.prod").write_text("BOT_TOKEN=x\n")
    targets = set_token.target_env_files(tmp_path, explicit=None)
    assert [p.name for p in targets] == [".env", ".env.prod"]


def test_target_env_files_defaults_to_env_only(tmp_path):
    targets = set_token.target_env_files(tmp_path, explicit=None)
    assert [p.name for p in targets] == [".env"]


def test_target_env_files_respects_explicit_path(tmp_path):
    targets = set_token.target_env_files(tmp_path, explicit=".env.prod")
    assert [p.name for p in targets] == [".env.prod"]
