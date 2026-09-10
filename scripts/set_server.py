#!/usr/bin/env python3
"""
Безопасный ввод данных сервера без участия агента.

IP-адрес, пароль и ключ никогда не проходят через чат с агентом:
1. Открывается страница на localhost с полями: адрес, порт, пользователь, пароль ИЛИ приватный ключ.
   Там же — ссылки, где арендовать сервер, если его ещё нет.
2. Скрипт проверяет вход по SSH, генерирует свой ключ ed25519 в .deploy/ и добавляет его
   в ~/.ssh/authorized_keys на сервере. Пароль на диск не записывается — он нужен один раз.
3. Скрипт проверяет вход по новому ключу и записывает .deploy/server.json (без секретов, кроме пути к ключу).

В stdout попадает только пользователь и адрес под маской: root@123.45.•.•

Usage:
    python scripts/set_server.py                                    # страница в браузере
    python scripts/set_server.py --host 1.2.3.4 --key-file ~/.ssh/id_ed25519 [--user root] [--port 22]
"""
from __future__ import annotations

import argparse
import html
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional

import providers
import server_config as sc

Connect = Callable[[sc.Credentials], sc.SshSession]


# ── разбор формы ─────────────────────────────────────────────────

def parse_form(form: Dict[str, List[str]]) -> sc.Credentials:
    """Проверить поля формы. Бросает ValueError с текстом для человека."""
    get = lambda key: (form.get(key) or [""])[0]  # noqa: E731
    host = get("host").strip()
    if not sc.valid_host(host):
        raise ValueError("Адрес сервера — это IP вроде 123.45.67.89 или домен. Без «ssh», «http://» и пробелов.")
    port = sc.parse_port(get("port"))
    user = get("user").strip() or "root"
    auth = get("auth").strip() or "password"
    if auth == "key":
        key_text = get("key").strip()
        if not sc.looks_like_private_key(key_text):
            raise ValueError("Это не похоже на приватный ключ: он начинается с «-----BEGIN … PRIVATE KEY-----».")
        return sc.Credentials(host=host, port=port, user=user, password=None, key_text=key_text + "\n")
    password = get("password")
    if not password:
        raise ValueError("Введите пароль от сервера (он приходит в письме от провайдера).")
    return sc.Credentials(host, port, user, password, None)


# ── страница ─────────────────────────────────────────────────────

PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Подключение сервера</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:560px;margin:50px auto;padding:0 20px;color:#222}}
  label{{display:block;margin-top:14px;font-weight:600}}
  input,textarea{{width:100%;font-size:16px;padding:10px;box-sizing:border-box;border:1px solid #bbb;border-radius:8px;margin-top:4px}}
  textarea{{height:120px;font-family:monospace;font-size:13px}}
  button{{margin-top:18px;font-size:18px;padding:12px 24px;border:0;border-radius:8px;background:#2a7fff;color:#fff;cursor:pointer}}
  .row{{display:flex;gap:12px}} .row>div{{flex:1}}
  .err{{color:#b00020;background:#fff0f0;padding:10px;border-radius:8px;margin:12px 0}}
  .hint{{color:#666;font-size:14px}}
  .rent{{background:#f6f8fa;padding:14px 16px;border-radius:10px;margin-bottom:10px}}
  .rent a{{margin-right:12px;white-space:nowrap}}
  fieldset{{border:1px solid #ddd;border-radius:8px;margin-top:14px}}
  .auth label{{display:inline;font-weight:400;margin-right:16px}}
</style></head><body>
<h1>Подключение сервера</h1>
<div class="rent">
  <b>Сервера ещё нет?</b> Арендуйте (подойдёт Ubuntu 22.04+, 1 ГБ RAM):<br>
  {providers}
  <div class="hint">Ссылки партнёрские: автор шаблона получает вознаграждение, цена для вас не меняется.</div>
</div>
<p class="hint">После создания сервера провайдер присылает IP-адрес и пароль root. Вставьте их сюда.
Данные не попадут в чат с агентом: скрипт проверит вход и переключит сервер на свой ключ.</p>
{error}
<form method="post">
  <div class="row">
    <div><label>IP-адрес или домен<input name="host" value="{host}" placeholder="123.45.67.89" autofocus autocomplete="off" spellcheck="false"></label></div>
    <div style="flex:0 0 100px"><label>Порт<input name="port" value="{port}" placeholder="22"></label></div>
  </div>
  <label>Пользователь<input name="user" value="{user}" placeholder="root"></label>
  <fieldset><legend>Как входить</legend>
    <div class="auth">
      <label><input type="radio" name="auth" value="password" {password_checked} onchange="sw()"> по паролю</label>
      <label><input type="radio" name="auth" value="key" {key_checked} onchange="sw()"> по приватному ключу</label>
    </div>
    <div id="pw"><label>Пароль<input name="password" type="password" autocomplete="off"></label></div>
    <div id="kt"><label>Приватный ключ<textarea name="key" placeholder="-----BEGIN OPENSSH PRIVATE KEY-----" spellcheck="false"></textarea></label></div>
  </fieldset>
  <button type="submit">Подключить</button>
</form>
<script>
function sw(){{var k=document.querySelector('input[name=auth][value=key]').checked;
document.getElementById('pw').style.display=k?'none':'';document.getElementById('kt').style.display=k?'':'none';}}
sw();
</script>
</body></html>"""

DONE_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Готово</title>
<style>body{{font-family:system-ui,sans-serif;max-width:520px;margin:60px auto;padding:0 20px;color:#222}}
.ok{{color:#0a7d2a;font-size:22px}}</style></head><body>
<p class="ok">✅ Сервер {server} подключён</p>
<p>Эту вкладку можно закрыть и вернуться к агенту.</p>
</body></html>"""


def render_form(error: str = "", values: Optional[Dict[str, str]] = None, auth: str = "password") -> str:
    values = values or {}
    links = " ".join(
        f'<a href="{html.escape(p.url)}" target="_blank" rel="noopener">{html.escape(p.name)}{" ★" if p is providers.PRIMARY else ""}</a>'
        for p in providers.PROVIDERS
    )
    return PAGE.format(
        providers=links,
        error=f'<p class="err">{html.escape(error)}</p>' if error else "",
        host=html.escape(values.get("host", "")), port=html.escape(values.get("port", "")),
        user=html.escape(values.get("user", "")),
        password_checked="" if auth == "key" else "checked", key_checked="checked" if auth == "key" else "",
    )


class ServerFormServer:
    """Локальный сервер с формой. Останавливается, как только вход на сервер удался."""

    def __init__(self, connect: Connect, host: str = "127.0.0.1"):
        self.connect = connect
        self.result: Optional[sc.Credentials] = None
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
                self._send(render_form())

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                form = urllib.parse.parse_qs(self.rfile.read(length).decode(), keep_blank_values=True)
                values = {k: (form.get(k) or [""])[0] for k in ("host", "port", "user")}
                auth = (form.get("auth") or ["password"])[0]
                try:
                    creds = parse_form(form)
                    check_login(creds, outer.connect)
                except (ValueError, sc.SshError) as e:
                    self._send(render_form(str(e), values, auth))
                    return
                outer.result = creds
                self._send(DONE_PAGE.format(server=html.escape(creds.describe())))
                threading.Thread(target=outer.shutdown, daemon=True).start()

        self._server = HTTPServer((host, 0), Handler)
        self.url = f"http://{host}:{self._server.server_address[1]}/"

    def serve_until_done(self, timeout: float = 600) -> Optional[sc.Credentials]:
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


def run_browser_form(connect: Connect, timeout: float = 600) -> Optional[sc.Credentials]:
    server = ServerFormServer(connect)
    print("🌐 Открываю страницу для ввода данных сервера в браузере…")
    print(f"   Если она не открылась сама, откройте вручную: {server.url}")
    webbrowser.open(server.url)
    return server.serve_until_done(timeout=timeout)


# ── установка ключа ──────────────────────────────────────────────

def check_login(creds: sc.Credentials, connect: Connect) -> None:
    """Подключиться и выполнить безобидную команду. Бросает SshError."""
    with connect(creds) as session:
        code, _ = session.run("echo ok")
    if code != 0:
        raise sc.SshError("Подключение есть, но команды не выполняются. Проверьте пользователя.")


def setup_server(root: Path, creds: sc.Credentials, project_name: str, connect: Connect) -> sc.ServerConfig:
    """Поставить наш ключ на сервер, проверить вход по нему и сохранить настройки. Пароль не сохраняется."""
    key_path = sc.deploy_dir(root) / sc.KEY_NAME
    _, pub_path = sc.generate_keypair(key_path, comment=f"{project_name}-deploy")
    public_key = pub_path.read_text(encoding="utf-8").strip()

    with connect(creds) as session:
        code, out = session.run(sc.authorized_keys_command(public_key))
    if code != 0:
        raise sc.SshError(f"Не удалось добавить ключ в authorized_keys: {out.strip()[:200]}")

    key_creds = sc.Credentials(host=creds.host, port=creds.port, user=creds.user, key_file=str(key_path))
    try:
        check_login(key_creds, connect)
    except sc.SshError as e:
        raise sc.SshError(f"Ключ добавлен, но вход по ключу не удался: {e}")

    cfg = sc.ServerConfig(
        host=creds.host, port=creds.port, user=creds.user, key_file=sc.KEY_NAME,
        project_path=sc.default_project_path(creds.user, project_name),
    )
    sc.save(root, cfg)
    return cfg


# ── CLI ──────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None, connect: Connect = sc.connect) -> int:
    parser = argparse.ArgumentParser(description="Безопасно подключить сервер для деплоя")
    parser.add_argument("--host", help="IP или домен (без браузера; пароль через CLI не принимается)")
    parser.add_argument("--port", default="22")
    parser.add_argument("--user", default="root")
    parser.add_argument("--key-file", help="существующий приватный ключ для первого входа")
    parser.add_argument("--project-name", default=None, help="имя папки проекта на сервере (по умолчанию — имя текущей папки)")
    parser.add_argument("--root", default=".")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--timeout", type=int, default=600, help="сколько секунд ждать ввода на странице")
    args = parser.parse_args(argv)

    missing = sc.missing_ssh_deps()
    if missing:
        print(f"❌ {missing}")
        return 1
    root = Path(args.root).resolve()
    project_name = args.project_name or root.name

    creds: Optional[sc.Credentials] = None
    try:
        if args.host:
            if not args.key_file:
                print("❌ Для режима без браузера нужен --key-file. Пароль через командную строку не принимается: just set-server")
                return 1
            creds = sc.Credentials(host=args.host.strip(), port=sc.parse_port(args.port), user=args.user,
                                   key_text=Path(args.key_file).expanduser().read_text(encoding="utf-8"))
            check_login(creds, connect)
        elif not args.no_browser:
            creds = run_browser_form(connect, timeout=args.timeout)
    except (ValueError, sc.SshError) as e:
        print(f"❌ {e}")
        return 1

    if creds is None:
        print("❌ Данные сервера не получены. Запустите ещё раз: just set-server")
        return 1

    try:
        cfg = setup_server(root, creds, project_name, connect)
    except sc.SshError as e:
        print(f"❌ {e}")
        return 1
    print(f"✅ Сервер {cfg.describe()} подключён (вход по ключу). Дальше: just deploy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
