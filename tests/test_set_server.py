"""
Тесты безопасного ввода данных сервера (scripts/set_server.py).
"""
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import server_config as sc  # noqa: E402
import set_server  # noqa: E402

KEY_TEXT = "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----\n"


class FakeSession:
    """Запоминает команды и загрузки. Вместо paramiko."""

    def __init__(self, creds, log):
        self.creds = creds
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, command, stream=False):
        self.log.append(("run", self.creds, command))
        return 0, ""

    def upload_bytes(self, data, remote_path, mode=0o600):
        self.log.append(("upload", remote_path, data))
        return None


def make_factory(log, fail_for=None):
    def factory(creds):
        if fail_for and fail_for(creds):
            raise sc.SshError("Authentication failed")
        return FakeSession(creds, log)
    return factory


def _post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read().decode()


# ── проверка полей формы ─────────────────────────────────────────

def test_parse_form_password():
    creds = set_server.parse_form({"host": ["1.2.3.4"], "port": [""], "user": [""], "auth": ["password"],
                                   "password": ["secret"], "key": [""]})
    assert creds == sc.Credentials(host="1.2.3.4", port=22, user="root", password="secret", key_text=None)


def test_parse_form_key_strips_and_validates():
    creds = set_server.parse_form({"host": [" bot.example.com "], "port": ["2222"], "user": ["deploy"],
                                   "auth": ["key"], "password": [""], "key": [KEY_TEXT]})
    assert creds.host == "bot.example.com" and creds.port == 2222 and creds.user == "deploy"
    assert creds.password is None and creds.key_text.startswith("-----BEGIN")


def test_parse_form_rejects_bad_host_port_and_empty_secret():
    for form in (
        {"host": ["ssh root@1.2.3.4"], "auth": ["password"], "password": ["x"]},
        {"host": ["1.2.3.4"], "port": ["99999"], "auth": ["password"], "password": ["x"]},
        {"host": ["1.2.3.4"], "auth": ["password"], "password": [""]},
        {"host": ["1.2.3.4"], "auth": ["key"], "key": ["not a key"]},
    ):
        try:
            set_server.parse_form(form)
        except ValueError:
            continue
        raise AssertionError(f"должно было упасть: {form}")


# ── страница ─────────────────────────────────────────────────────

def test_form_page_has_fields_and_partner_links():
    page = set_server.render_form()
    for name in ('name="host"', 'name="port"', 'name="user"', 'name="password"', 'name="key"'):
        assert name in page
    assert "vdska.ru" in page and "партнёрск" in page.lower()


def test_form_server_accepts_credentials_after_successful_connect_and_stops():
    log = []
    server = set_server.ServerFormServer(connect=make_factory(log))
    thread = threading.Thread(target=server.serve_until_done, kwargs={"timeout": 5})
    thread.start()

    page = urllib.request.urlopen(server.url, timeout=5).read().decode()
    assert "<form" in page

    response = _post(server.url, {"host": "1.2.3.4", "port": "", "user": "", "auth": "password",
                                  "password": "secret", "key": ""})
    thread.join(timeout=5)

    assert "подключ" in response.lower()
    assert server.result == sc.Credentials("1.2.3.4", 22, "root", "secret", None)
    assert not thread.is_alive()
    assert log and log[0][0] == "run"  # проверочная команда выполнена


def test_form_server_shows_error_when_connect_fails_and_keeps_waiting():
    log = []
    server = set_server.ServerFormServer(connect=make_factory(log, fail_for=lambda c: True))
    thread = threading.Thread(target=server.serve_until_done, kwargs={"timeout": 5})
    thread.start()

    response = _post(server.url, {"host": "1.2.3.4", "auth": "password", "password": "wrong"})
    assert "<form" in response and "Authentication failed" in response
    assert server.result is None
    assert thread.is_alive()

    server.shutdown()
    thread.join(timeout=5)


def test_form_server_shows_validation_error():
    log = []
    server = set_server.ServerFormServer(connect=make_factory(log))
    thread = threading.Thread(target=server.serve_until_done, kwargs={"timeout": 5})
    thread.start()

    response = _post(server.url, {"host": "ssh root@1.2.3.4", "auth": "password", "password": "x"})
    assert "<form" in response and 'value="ssh root@1.2.3.4"' in response
    assert server.result is None and log == []

    server.shutdown()
    thread.join(timeout=5)


# ── установка ключа ──────────────────────────────────────────────

def test_setup_server_installs_generated_key_and_saves_config(tmp_path):
    log = []
    creds = sc.Credentials("123.45.67.89", 22, "root", "secret", None)

    cfg = set_server.setup_server(tmp_path, creds, project_name="my_bot", connect=make_factory(log))

    assert cfg == sc.ServerConfig("123.45.67.89", 22, "root", "deploy_key", "/root/my_bot")
    assert sc.load(tmp_path) == cfg
    pub = (tmp_path / ".deploy" / "deploy_key.pub").read_text().strip()
    installs = [c for kind, _, c in log if kind == "run" and pub in c]
    assert installs, "публичный ключ не был добавлен в authorized_keys"
    # первое подключение — по паролю, проверочное — по нашему ключу без пароля
    assert log[0][1].password == "secret"
    assert log[-1][1].password is None and log[-1][1].key_file == str(cfg.key_path(tmp_path))


def test_setup_server_never_writes_password_to_disk(tmp_path):
    creds = sc.Credentials("1.2.3.4", 22, "root", "hunter2-very-secret", None)
    set_server.setup_server(tmp_path, creds, project_name="b", connect=make_factory([]))
    for path in (tmp_path / ".deploy").iterdir():
        assert "hunter2-very-secret" not in path.read_text()


def test_setup_server_raises_when_key_login_fails(tmp_path):
    creds = sc.Credentials("1.2.3.4", 22, "root", "secret", None)
    factory = make_factory([], fail_for=lambda c: c.password is None)
    try:
        set_server.setup_server(tmp_path, creds, project_name="b", connect=factory)
    except sc.SshError as e:
        assert "ключ" in str(e).lower()
    else:
        raise AssertionError("ожидалась ошибка входа по ключу")
    assert sc.load(tmp_path) is None


# ── CLI ──────────────────────────────────────────────────────────

def test_main_cli_mode_with_key_file(tmp_path, capsys):
    key = tmp_path / "id"
    key.write_text(KEY_TEXT)
    log = []
    code = set_server.main(["--host", "123.45.67.89", "--user", "deploy", "--key-file", str(key),
                            "--root", str(tmp_path), "--project-name", "my_bot"], connect=make_factory(log))
    out = capsys.readouterr().out
    assert code == 0
    assert "deploy@123.45.•.•" in out and "67.89" not in out
    assert sc.load(tmp_path).project_path == "/home/deploy/my_bot"


def test_main_reports_failure_without_credentials(tmp_path, capsys):
    code = set_server.main(["--root", str(tmp_path), "--no-browser"], connect=make_factory([]))
    assert code == 1
    assert "set-server" in capsys.readouterr().out


def test_main_explains_missing_deps(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "missing_ssh_deps", lambda importer=None: "Нет paramiko. Выполните: just venv")
    code = set_server.main(["--root", str(tmp_path)], connect=make_factory([]))
    assert code == 1
    assert "just venv" in capsys.readouterr().out
