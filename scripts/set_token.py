#!/usr/bin/env python3
"""
Безопасный ввод BOT_TOKEN без участия агента.

Токен никогда не печатается целиком и не проходит через чат с агентом:
1. Скрипт пробует взять токен из буфера обмена (человек только что скопировал его у @BotFather).
   Принимается только строка в формате токена, прошедшая проверку getMe. Всё остальное игнорируется.
2. Если в буфере нет токена, открывается страница на localhost с одним видимым полем ввода.
3. Токен проверяется через Telegram API и записывается в .env (права 600).

В stdout попадает только имя бота и замаскированный хвост токена.

Usage:
    python scripts/set_token.py            # буфер обмена, затем браузер
    python scripts/set_token.py --no-clipboard
    python scripts/set_token.py --no-browser   # только буфер обмена
    python scripts/set_token.py --env .env.prod
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Optional, Tuple

TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,60}$")
TokenResult = Optional[Tuple[str, str]]  # (token, bot_username)


# ── чистые функции ───────────────────────────────────────────────

def looks_like_token(value: str) -> bool:
    """Строка похожа на токен Telegram-бота."""
    return bool(TOKEN_RE.match((value or "").strip()))


def mask(token: str) -> str:
    """Замаскировать токен для вывода: видны только 4 первых и 3 последних символа."""
    return f"{token[:4]}…{token[-3:]}"


def write_env(env_path: Path, example_path: Path, token: str, username: str) -> None:
    """Записать BOT_TOKEN и BOT_USERNAME в .env, создав его из .env.example при необходимости."""
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
    elif example_path.exists():
        content = example_path.read_text(encoding="utf-8")
    else:
        content = ""

    lines = content.splitlines()
    updates = {"BOT_TOKEN": token, "BOT_USERNAME": username}
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in updates:
            lines[i] = f"{key}={updates[key]}"
            seen.add(key)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass


# ── внешний мир ──────────────────────────────────────────────────

def verify_with_telegram(token: str) -> Optional[str]:
    """Проверить токен через getMe. Возвращает username бота или None."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    if data.get("ok") and data.get("result", {}).get("username"):
        return data["result"]["username"]
    return None


def read_system_clipboard() -> str:
    """Прочитать буфер обмена. Бросает исключение, если инструмента нет."""
    if sys.platform == "darwin":
        cmd = ["pbpaste"]
    elif sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
    elif os.environ.get("WAYLAND_DISPLAY"):
        cmd = ["wl-paste", "--no-newline"]
    else:
        cmd = ["xclip", "-selection", "clipboard", "-o"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
    return result.stdout


def token_from_clipboard(
    read_clipboard: Callable[[], str],
    verify: Callable[[str], Optional[str]],
) -> TokenResult:
    """Взять токен из буфера обмена, если там лежит именно токен и Telegram его принимает."""
    try:
        raw = read_clipboard()
    except Exception:
        return None
    if not looks_like_token(raw):
        return None
    token = raw.strip()
    username = verify(token)
    if not username:
        return None
    return token, username


# ── страница в браузере ──────────────────────────────────────────

PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Подключение бота</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:520px;margin:60px auto;padding:0 20px;color:#222}}
  input{{width:100%;font-size:18px;padding:12px;box-sizing:border-box;border:1px solid #bbb;border-radius:8px}}
  button{{margin-top:14px;font-size:18px;padding:12px 24px;border:0;border-radius:8px;background:#2a7fff;color:#fff;cursor:pointer}}
  .err{{color:#b00020;margin:12px 0}} .ok{{color:#0a7d2a;font-size:22px}} code{{background:#f2f2f2;padding:2px 6px;border-radius:4px}}
</style></head><body>
<h1>Подключение Telegram-бота</h1>
<p>Откройте в Telegram <b>@BotFather</b>, отправьте <code>/newbot</code> (или <code>/token</code> для существующего бота),
скопируйте токен и вставьте его в поле ниже.</p>
{error}
<form method="post">
  <input name="token" placeholder="123456789:AAH..." autofocus autocomplete="off" spellcheck="false">
  <button type="submit">Сохранить</button>
</form>
</body></html>"""

DONE_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Готово</title>
<style>body{{font-family:system-ui,sans-serif;max-width:520px;margin:60px auto;padding:0 20px;color:#222}}
.ok{{color:#0a7d2a;font-size:22px}}</style></head><body>
<p class="ok">✅ Бот @{username} подключён</p>
<p>Эту вкладку можно закрыть и вернуться к агенту.</p>
</body></html>"""


class TokenFormServer:
    """Локальный сервер с одним полем ввода. Останавливается, как только получил валидный токен."""

    def __init__(self, verify: Callable[[str], Optional[str]], host: str = "127.0.0.1"):
        self.verify = verify
        self.result: TokenResult = None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # тишина в stdout
                pass

            def _send(self, body: str, status: int = 200):
                data = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._send(PAGE.format(error=""))

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                form = urllib.parse.parse_qs(self.rfile.read(length).decode())
                token = (form.get("token") or [""])[0].strip()
                if not looks_like_token(token):
                    self._send(PAGE.format(error='<p class="err">Это не похоже на токен. Скопируйте его у @BotFather целиком.</p>'))
                    return
                username = outer.verify(token)
                if not username:
                    self._send(PAGE.format(error='<p class="err">Telegram не принял этот токен. Проверьте, что он скопирован без лишних символов.</p>'))
                    return
                outer.result = (token, username)
                self._send(DONE_PAGE.format(username=html.escape(username)))
                threading.Thread(target=outer.shutdown, daemon=True).start()

        self._server = HTTPServer((host, 0), Handler)
        self.url = f"http://{host}:{self._server.server_address[1]}/"

    def serve_until_token(self, timeout: float = 300) -> TokenResult:
        timer = threading.Timer(timeout, self.shutdown)
        timer.daemon = True
        timer.start()
        try:
            self._server.serve_forever(poll_interval=0.1)
        finally:
            timer.cancel()
            self._server.server_close()
        return self.result

    def shutdown(self) -> None:
        self._server.shutdown()


def run_browser_form(verify: Callable[[str], Optional[str]], timeout: float = 300) -> TokenResult:
    server = TokenFormServer(verify)
    print("🌐 Открываю страницу для ввода токена в браузере…")
    print(f"   Если она не открылась сама, откройте вручную: {server.url}")
    webbrowser.open(server.url)
    return server.serve_until_token(timeout=timeout)


# ── сценарий ─────────────────────────────────────────────────────

def target_env_files(root: Path, explicit: Optional[str]) -> list[Path]:
    """Куда писать токен: явный путь, иначе .env и (если уже есть) .env.prod."""
    if explicit:
        return [root / explicit]
    targets = [root / ".env"]
    if (root / ".env.prod").exists():
        targets.append(root / ".env.prod")
    return targets


def obtain_token(
    read_clipboard: Optional[Callable[[], str]],
    verify: Callable[[str], Optional[str]],
    run_form: Optional[Callable[[], TokenResult]],
) -> TokenResult:
    """Сначала буфер обмена, затем страница в браузере."""
    if read_clipboard is not None:
        found = token_from_clipboard(read_clipboard, verify)
        if found:
            return found
    if run_form is not None:
        return run_form()
    return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Безопасно сохранить BOT_TOKEN в .env")
    parser.add_argument("--env", default=None, help="файл для записи (по умолчанию .env и, если есть, .env.prod)")
    parser.add_argument("--no-clipboard", action="store_true", help="не читать буфер обмена")
    parser.add_argument("--no-browser", action="store_true", help="не открывать страницу в браузере")
    parser.add_argument("--timeout", type=int, default=300, help="сколько секунд ждать ввода на странице")
    args = parser.parse_args(argv)

    root = Path(".")
    targets = target_env_files(root, args.env)
    example_path = root / ".env.example"

    result = obtain_token(
        read_clipboard=None if args.no_clipboard else read_system_clipboard,
        verify=verify_with_telegram,
        run_form=None if args.no_browser else (lambda: run_browser_form(verify_with_telegram, args.timeout)),
    )
    if not result:
        print("❌ Токен не получен. Скопируйте токен у @BotFather и запустите команду ещё раз.")
        return 1

    token, username = result
    for env_path in targets:
        write_env(env_path, example_path, token, username)
    print(f"✅ Бот @{username} подключён. Токен {mask(token)} записан в {', '.join(str(t) for t in targets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
