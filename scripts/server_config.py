#!/usr/bin/env python3
"""
Общий слой для работы с сервером: настройки в .deploy/server.json, маскирование, SSH-ключи
и тонкая обёртка над paramiko. Используется set_server.py, remote_deploy.py, github_secrets.py, doctor.py.

Секреты (ключ) живут только в .deploy/ — папка в .gitignore и запрещена к чтению агенту.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Tuple

DEPLOY_DIR = ".deploy"
CONFIG_NAME = "server.json"
KEY_NAME = "deploy_key"

HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$", re.IGNORECASE)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


# ── чистые функции ───────────────────────────────────────────────

def mask_host(host: str) -> str:
    """'123.45.67.89' → '123.45.•.•'; 'srv.example.com' → 'srv…example.com'. Чтобы адрес не утекал в чат."""
    host = (host or "").strip()
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.•.•"
    if len(parts) >= 2:
        return f"{host[:3]}…{'.'.join(parts[-2:])}"
    return "•••"


def valid_host(host: str) -> bool:
    """IP-адрес (v4/v6) или доменное имя. Без 'ssh', 'http://' и прочего мусора."""
    value = (host or "").strip()
    if not value:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        pass
    return bool(HOSTNAME_RE.match(value))


def parse_port(raw: str) -> int:
    value = (raw or "").strip()
    if not value:
        return 22
    if not value.isdigit() or not 1 <= int(value) <= 65535:
        raise ValueError(f"Порт должен быть числом от 1 до 65535, а не «{raw}»")
    return int(value)


def looks_like_private_key(text: str) -> bool:
    return bool(PRIVATE_KEY_RE.search(text or ""))


def default_project_path(user: str, project_name: str) -> str:
    home = "/root" if user == "root" else f"/home/{user}"
    return f"{home}/{project_name}"


def authorized_keys_command(public_key: str) -> str:
    """Shell-команда для сервера: добавить публичный ключ в ~/.ssh/authorized_keys, если его там ещё нет."""
    key = shlex.quote(public_key.strip())
    return (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        f"(grep -qF {key} ~/.ssh/authorized_keys || echo {key} >> ~/.ssh/authorized_keys) && "
        "chmod 600 ~/.ssh/authorized_keys"
    )


# ── конфигурация ─────────────────────────────────────────────────

@dataclass
class ServerConfig:
    host: str
    port: int
    user: str
    key_file: str
    project_path: str

    def describe(self) -> str:
        suffix = "" if self.port == 22 else f":{self.port}"
        return f"{self.user}@{mask_host(self.host)}{suffix}"

    def key_path(self, root: Path) -> Path:
        """Относительное имя — внутри .deploy/; абсолютный путь (CI) — как есть."""
        path = Path(self.key_file).expanduser()
        return path if path.is_absolute() else root / DEPLOY_DIR / self.key_file


def deploy_dir(root: Path) -> Path:
    path = root / DEPLOY_DIR
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def save(root: Path, cfg: ServerConfig) -> Path:
    path = deploy_dir(root) / CONFIG_NAME
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def load(root: Path) -> Optional[ServerConfig]:
    path = root / DEPLOY_DIR / CONFIG_NAME
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ServerConfig(**{k: data[k] for k in ServerConfig.__dataclass_fields__})


# ── ключи ────────────────────────────────────────────────────────

def generate_keypair(private_path: Path, comment: str = "deploy") -> Tuple[Path, Path]:
    """Создать ключ ed25519 в формате OpenSSH. Существующий ключ не перезаписывается."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    public_path = private_path.with_name(private_path.name + ".pub")
    if private_path.exists() and public_path.exists():
        return private_path, public_path

    private_path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()
    )
    public_bytes = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)

    private_path.write_bytes(private_bytes)
    public_path.write_text(f"{public_bytes.decode()} {comment}\n", encoding="utf-8")
    for path, mode in ((private_path, 0o600), (public_path, 0o644)):
        try:
            os.chmod(path, mode)
        except OSError:
            pass
    return private_path, public_path


# ── SSH ──────────────────────────────────────────────────────────

class SshError(Exception):
    """Не удалось подключиться или выполнить команду по SSH. Текст безопасен для показа."""


def missing_ssh_deps(importer=None) -> Optional[str]:
    """Сообщение для человека, если нет paramiko/cryptography; None — всё на месте."""
    import importlib

    importer = importer or importlib.import_module
    try:
        importer("paramiko")
        importer("cryptography")
    except ImportError:
        return "Нет библиотеки paramiko для SSH. Выполните один раз: just venv — и повторите команду."
    return None


@dataclass
class Credentials:
    """Чем подключаемся. Пароль или текст ключа живут только в памяти процесса."""
    host: str
    port: int = 22
    user: str = "root"
    password: Optional[str] = None
    key_text: Optional[str] = None
    key_file: Optional[str] = None

    def describe(self) -> str:
        suffix = "" if self.port == 22 else f":{self.port}"
        return f"{self.user}@{mask_host(self.host)}{suffix}"


class SshSession:
    """Тонкая обёртка над paramiko: run() и upload_bytes(). Используется как контекстный менеджер."""

    def __init__(self, creds: Credentials, timeout: float = 20):
        self.creds = creds
        self.timeout = timeout
        self._client = None

    def __enter__(self) -> SshSession:
        import io

        try:
            import paramiko
        except ImportError:
            raise SshError("Нет библиотеки paramiko. Выполните: just venv")

        pkey = None
        try:
            if self.creds.key_text:
                pkey = _load_pkey(paramiko, io.StringIO(self.creds.key_text))
            elif self.creds.key_file:
                with open(self.creds.key_file, encoding="utf-8") as fh:
                    pkey = _load_pkey(paramiko, fh)
        except Exception as e:  # noqa: BLE001 — любая ошибка чтения ключа
            raise SshError(f"Не удалось прочитать приватный ключ: {type(e).__name__}")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            auth = {"password": self.creds.password, "pkey": pkey}
            client.connect(
                self.creds.host, port=self.creds.port, username=self.creds.user, **auth,
                allow_agent=False, look_for_keys=False, timeout=self.timeout, banner_timeout=self.timeout,
            )
        except paramiko.AuthenticationException:
            raise SshError("Сервер не принял пароль или ключ. Проверьте пользователя и пароль из письма провайдера.")
        except Exception as e:  # noqa: BLE001 — сетевые ошибки любого вида
            raise SshError(f"Не удалось подключиться к {self.creds.describe()}: {type(e).__name__}: {e}")
        self._client = client
        return self

    def __exit__(self, *exc) -> bool:
        if self._client is not None:
            self._client.close()
        return False

    def run(self, command: str, stream: bool = False) -> Tuple[int, str]:
        """Выполнить команду. При stream=True вывод печатается по мере появления."""
        _, stdout, _ = self._client.exec_command(command, get_pty=True)
        chunks = []
        for line in iter(stdout.readline, ""):
            chunks.append(line)
            if stream:
                print("   " + line.rstrip())
        code = stdout.channel.recv_exit_status()
        return code, "".join(chunks)

    def upload_bytes(self, data: bytes, remote_path: str, mode: int = 0o600) -> None:
        import io

        sftp = self._client.open_sftp()
        try:
            sftp.putfo(io.BytesIO(data), remote_path)
            sftp.chmod(remote_path, mode)
        finally:
            sftp.close()


def _load_pkey(paramiko, fh):
    """Загрузить ключ любого поддерживаемого типа из файлового объекта."""
    text = fh.read()
    import io

    last = None
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            return cls.from_private_key(io.StringIO(text))
        except Exception as e:  # noqa: BLE001
            last = e
    raise last or ValueError("unknown key type")


def connect(creds: Credentials) -> SshSession:
    """Фабрика сессии. В тестах подменяется фейком."""
    return SshSession(creds)
