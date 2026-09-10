"""
Тесты общего слоя настроек сервера (scripts/server_config.py).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import server_config as sc  # noqa: E402

# ── маска хоста ──────────────────────────────────────────────────

@pytest.mark.parametrize("host,expected", [
    ("123.45.67.89", "123.45.•.•"),
    ("server.example.com", "ser…example.com"),
    ("abc", "•••"),
])
def test_mask_host(host, expected):
    assert sc.mask_host(host) == expected


# ── валидация ────────────────────────────────────────────────────

@pytest.mark.parametrize("host", ["123.45.67.89", "bot.example.com", "2001:db8::1"])
def test_valid_host_accepts_ip_and_domain(host):
    assert sc.valid_host(host)


@pytest.mark.parametrize("host", ["", "ssh root@1.2.3.4", "http://1.2.3.4", "1.2.3", "hello world"])
def test_valid_host_rejects_junk(host):
    assert not sc.valid_host(host)


def test_parse_port_defaults_and_bounds():
    assert sc.parse_port("") == 22
    assert sc.parse_port("2222") == 2222
    with pytest.raises(ValueError):
        sc.parse_port("70000")
    with pytest.raises(ValueError):
        sc.parse_port("abc")


def test_looks_like_private_key():
    assert sc.looks_like_private_key("-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----")
    assert sc.looks_like_private_key("-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----")
    assert not sc.looks_like_private_key("my password")
    assert not sc.looks_like_private_key("ssh-ed25519 AAAA... user@host")  # публичный, не приватный


# ── конфигурация ─────────────────────────────────────────────────

def test_save_and_load_roundtrip(tmp_path):
    cfg = sc.ServerConfig(host="1.2.3.4", port=22, user="root", key_file="deploy_key", project_path="/root/my_bot")
    path = sc.save(tmp_path, cfg)
    assert path == tmp_path / ".deploy" / "server.json"
    assert sc.load(tmp_path) == cfg
    data = json.loads(path.read_text())
    assert data["host"] == "1.2.3.4"


def test_load_returns_none_when_missing(tmp_path):
    assert sc.load(tmp_path) is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
def test_save_restricts_permissions(tmp_path):
    cfg = sc.ServerConfig(host="1.2.3.4", port=22, user="root", key_file="deploy_key", project_path="/root/x")
    path = sc.save(tmp_path, cfg)
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_config_describe_is_masked():
    cfg = sc.ServerConfig(host="123.45.67.89", port=22, user="root", key_file="deploy_key", project_path="/root/x")
    text = cfg.describe()
    assert "root@123.45.•.•" in text
    assert "67.89" not in text


def test_key_path_is_inside_deploy_dir(tmp_path):
    cfg = sc.ServerConfig(host="1.2.3.4", port=22, user="root", key_file="deploy_key", project_path="/root/x")
    assert cfg.key_path(tmp_path) == tmp_path / ".deploy" / "deploy_key"


def test_default_project_path_uses_project_name_and_home():
    assert sc.default_project_path("root", "my_bot") == "/root/my_bot"
    assert sc.default_project_path("deploy", "my_bot") == "/home/deploy/my_bot"


# ── ключи ────────────────────────────────────────────────────────

def test_generate_keypair_writes_openssh_files(tmp_path):
    priv, pub = sc.generate_keypair(tmp_path / ".deploy" / "deploy_key", comment="my_bot-deploy")
    assert priv.read_text().startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert pub.read_text().startswith("ssh-ed25519 ")
    assert pub.read_text().strip().endswith("my_bot-deploy")
    if sys.platform != "win32":
        assert priv.stat().st_mode & 0o777 == 0o600


def test_generate_keypair_does_not_overwrite_existing(tmp_path):
    priv, _ = sc.generate_keypair(tmp_path / "k")
    first = priv.read_text()
    sc.generate_keypair(tmp_path / "k")
    assert priv.read_text() == first


def test_authorized_keys_command_appends_key_once():
    cmd = sc.authorized_keys_command("ssh-ed25519 AAAA test")
    assert "mkdir -p ~/.ssh" in cmd
    assert "chmod 700 ~/.ssh" in cmd
    assert "grep -qF" in cmd  # не дублировать ключ
    assert "ssh-ed25519 AAAA test" in cmd
    assert "chmod 600 ~/.ssh/authorized_keys" in cmd


# ── зависимости и реальное подключение ───────────────────────────

def test_missing_ssh_deps_returns_hint_when_import_fails():
    def importer(name):
        raise ImportError(name)
    message = sc.missing_ssh_deps(importer)
    assert message and "just venv" in message


def test_missing_ssh_deps_is_none_when_available():
    assert sc.missing_ssh_deps() is None


def test_ssh_session_raises_ssh_error_when_connection_refused():
    creds = sc.Credentials(host="127.0.0.1", port=1, user="nobody", password="x")
    with pytest.raises(sc.SshError) as info:
        with sc.SshSession(creds, timeout=2):
            pass
    assert "127.0.•.•" in str(info.value) and "nobody" in str(info.value)


def test_ssh_session_loads_generated_key(tmp_path):
    priv, _ = sc.generate_keypair(tmp_path / "k")
    import paramiko
    with open(priv, encoding="utf-8") as fh:
        key = sc._load_pkey(paramiko, fh)
    assert key.get_name() == "ssh-ed25519"
