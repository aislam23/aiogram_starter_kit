"""
Тесты публикации секретов деплоя в GitHub Actions через gh CLI (scripts/github_secrets.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import github_secrets as gs  # noqa: E402
import server_config as sc  # noqa: E402


def _setup(tmp_path):
    cfg = sc.ServerConfig("123.45.67.89", 2222, "root", "deploy_key", "/root/my_bot")
    sc.save(tmp_path, cfg)
    (tmp_path / ".deploy" / "deploy_key").write_text("PRIVATE-KEY-BODY\n")
    (tmp_path / ".env.prod").write_text("BOT_TOKEN=prod\n")
    return cfg


def test_collect_secrets_reads_key_and_env_prod(tmp_path):
    cfg = _setup(tmp_path)
    secrets = gs.collect_secrets(tmp_path, cfg)
    assert secrets == {
        "SERVER_HOST": "123.45.67.89",
        "SERVER_PORT": "2222",
        "SERVER_USER": "root",
        "SSH_PRIVATE_KEY": "PRIVATE-KEY-BODY\n",
        "PROJECT_PATH": "/root/my_bot",
        "ENV_PROD": "BOT_TOKEN=prod\n",
    }


def test_publish_passes_values_via_stdin_not_argv(tmp_path):
    cfg = _setup(tmp_path)
    calls = []

    def runner(cmd, input_text=None):
        calls.append((cmd, input_text))
        return 0, ""

    names = gs.publish(gs.collect_secrets(tmp_path, cfg), runner)
    assert names == ["SERVER_HOST", "SERVER_PORT", "SERVER_USER", "SSH_PRIVATE_KEY", "PROJECT_PATH", "ENV_PROD"]
    for cmd, _input_text in calls:
        assert cmd[:3] == ["gh", "secret", "set"]
        assert "PRIVATE-KEY-BODY" not in " ".join(cmd)
    key_call = next(c for c in calls if c[0][3] == "SSH_PRIVATE_KEY")
    assert key_call[1] == "PRIVATE-KEY-BODY\n"


def test_check_gh_reports_missing_cli_auth_and_remote():
    def runner(cmd, input_text=None):
        if cmd[:2] == ["gh", "auth"]:
            return 1, "not logged in"
        return 0, "ok"

    problems = gs.check_gh(runner)
    assert any("gh auth login" in p for p in problems)

    assert gs.check_gh(lambda cmd, input_text=None: (0, "ok")) == []

    def no_remote(cmd, input_text=None):
        return (1, "") if cmd[:2] == ["git", "remote"] else (0, "ok")

    assert any("origin" in p for p in gs.check_gh(no_remote))


def test_main_prints_only_names_and_masked_host(tmp_path, capsys):
    _setup(tmp_path)
    code = gs.main(["--root", str(tmp_path)], runner=lambda cmd, input_text=None: (0, "ok"))
    out = capsys.readouterr().out
    assert code == 0
    assert "SSH_PRIVATE_KEY" in out and "PRIVATE-KEY-BODY" not in out
    assert "123.45.•.•" in out and "67.89" not in out


def test_main_fails_without_server_config(tmp_path, capsys):
    code = gs.main(["--root", str(tmp_path)], runner=lambda cmd, input_text=None: (0, "ok"))
    assert code == 1
    assert "set-server" in capsys.readouterr().out
