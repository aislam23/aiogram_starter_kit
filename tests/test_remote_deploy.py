"""
Тесты деплоя по SSH с локальной машины (scripts/remote_deploy.py).
"""
import io
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import remote_deploy as rd  # noqa: E402
import server_config as sc  # noqa: E402


class FakeSession:
    def __init__(self, creds, log, outputs=None):
        self.creds, self.log, self.outputs = creds, log, outputs or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, command, stream=False):
        self.log.append(("run", command))
        for key, (code, out) in self.outputs.items():
            if key in command:
                return code, out
        return 0, ""

    def upload_bytes(self, data, remote_path, mode=0o600):
        self.log.append(("upload", remote_path, data))


def _project(tmp_path) -> Path:
    for rel, text in {
        "app/main.py": "print(1)\n",
        "scripts/deploy.py": "pass\n",
        "docker-compose.prod.yml": "services: {}\n",
        ".env": "BOT_TOKEN=secret\n",
        ".env.prod": "BOT_TOKEN=prod\n",
        ".env.example": "BOT_TOKEN=\n",
        ".deploy/server.json": "{}",
        ".deploy/deploy_key": "key",
        "logs/bot.jsonl": "{}",
        ".venv/lib/x.py": "",
        "app/__pycache__/x.pyc": "",
    }.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path


# ── состав архива ────────────────────────────────────────────────

def test_project_files_fallback_walk_excludes_secrets_and_junk(tmp_path):
    root = _project(tmp_path)
    files = {str(p) for p in rd.project_files(root, runner=lambda cmd, cwd: (1, ""))}
    assert {"app/main.py", "scripts/deploy.py", "docker-compose.prod.yml", ".env.example"} <= files
    for banned in (".env", ".env.prod", ".deploy/server.json", ".deploy/deploy_key", "logs/bot.jsonl",
                   ".venv/lib/x.py", "app/__pycache__/x.pyc"):
        assert banned not in files


def test_project_files_uses_git_ls_files_when_available(tmp_path):
    root = _project(tmp_path)
    git_out = "app/main.py\n.env.prod\n.deploy/deploy_key\nscripts/deploy.py\n"
    files = {str(p) for p in rd.project_files(root, runner=lambda cmd, cwd: (0, git_out))}
    assert files == {"app/main.py", "scripts/deploy.py"}


def test_build_tarball_contains_files_with_relative_paths(tmp_path):
    root = _project(tmp_path)
    data = rd.build_tarball(root, [Path("app/main.py"), Path("scripts/deploy.py")])
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        assert sorted(tar.getnames()) == ["app/main.py", "scripts/deploy.py"]


# ── команды на сервере ───────────────────────────────────────────

def test_deploy_script_extracts_and_runs_server_side_deploy():
    script = rd.deploy_script("/root/my_bot", "/tmp/my_bot.tar.gz")
    assert "mkdir -p /root/my_bot" in script
    assert "tar" in script and "/tmp/my_bot.tar.gz" in script
    assert "python3 scripts/deploy.py --ci" in script


def test_ensure_docker_script_installs_only_when_missing():
    script = rd.ensure_docker_script()
    assert "command -v docker" in script
    assert "get.docker.com" in script


# ── сценарий ─────────────────────────────────────────────────────

def _cfg():
    return sc.ServerConfig("123.45.67.89", 22, "root", "deploy_key", "/root/my_bot")


def test_deploy_uploads_project_and_env_prod_then_runs_deploy(tmp_path, capsys):
    root = _project(tmp_path)
    log = []
    code = rd.deploy(root, _cfg(), connect=lambda creds: FakeSession(creds, log),
                     runner=lambda cmd, cwd: (1, ""))
    out = capsys.readouterr().out
    assert code == 0
    uploads = {entry[1]: entry[2] for entry in log if entry[0] == "upload"}
    assert "/root/my_bot/.env.prod" in uploads and uploads["/root/my_bot/.env.prod"] == b"BOT_TOKEN=prod\n"
    tar_paths = [p for p in uploads if p.endswith(".tar.gz")]
    assert tar_paths
    with tarfile.open(fileobj=io.BytesIO(uploads[tar_paths[0]]), mode="r:gz") as tar:
        names = tar.getnames()
    assert "app/main.py" in names and ".env" not in names and ".env.prod" not in names
    runs = [c for kind, *rest in log for c in rest[:1] if kind == "run"]
    assert any("get.docker.com" in c for c in runs)
    assert any("scripts/deploy.py --ci" in c for c in runs)
    assert "root@123.45.•.•" in out and "67.89" not in out


def test_deploy_fails_without_env_prod(tmp_path, capsys):
    root = _project(tmp_path)
    (root / ".env.prod").unlink()
    code = rd.deploy(root, _cfg(), connect=lambda creds: FakeSession(creds, []), runner=lambda c, cwd: (1, ""))
    assert code == 1
    assert "just init" in capsys.readouterr().out


def test_deploy_returns_remote_exit_code(tmp_path):
    root = _project(tmp_path)
    outputs = {"scripts/deploy.py --ci": (1, "boom")}
    code = rd.deploy(root, _cfg(), connect=lambda creds: FakeSession(creds, [], outputs), runner=lambda c, cwd: (1, ""))
    assert code == 1


def test_deploy_connects_with_key_from_config(tmp_path):
    root = _project(tmp_path)
    seen = []

    def connect(creds):
        seen.append(creds)
        return FakeSession(creds, [])

    rd.deploy(root, _cfg(), connect=connect, runner=lambda c, cwd: (1, ""))
    assert seen[0].key_file == str(root / ".deploy" / "deploy_key") and seen[0].password is None


def test_logs_and_status_run_compose_commands_in_project_path():
    log = []
    rd.logs(_cfg(), 30, connect=lambda creds: FakeSession(creds, log))
    rd.status(_cfg(), connect=lambda creds: FakeSession(creds, log))
    commands = [c for kind, c in log]
    assert any("cd /root/my_bot" in c and "logs" in c and "30" in c for c in commands)
    assert any("cd /root/my_bot" in c and " ps" in c for c in commands)


# ── источник настроек ────────────────────────────────────────────

def test_resolve_config_prefers_cli_args_over_file(tmp_path):
    sc.save(tmp_path, _cfg())
    cfg = rd.resolve_config(tmp_path, host="9.9.9.9", port="2222", user="deploy", key_file="/tmp/k", project_path="")
    assert cfg.host == "9.9.9.9" and cfg.port == 2222 and cfg.user == "deploy"
    assert cfg.project_path == "/home/deploy/" + tmp_path.name
    assert cfg.key_path(tmp_path) == Path("/tmp/k")


def test_resolve_config_falls_back_to_saved_file(tmp_path):
    sc.save(tmp_path, _cfg())
    assert rd.resolve_config(tmp_path) == _cfg()


def test_resolve_config_returns_none_when_nothing_configured(tmp_path):
    assert rd.resolve_config(tmp_path) is None


def test_main_without_config_explains_set_server(tmp_path, capsys):
    code = rd.main(["deploy", "--root", str(tmp_path)], connect=lambda c: FakeSession(c, []))
    assert code == 1
    assert "set-server" in capsys.readouterr().out
