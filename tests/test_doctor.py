"""
Тесты диагностики окружения (scripts/doctor.py).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import doctor  # noqa: E402

TOKEN = "123456789:AAHfiqksKZ8WmR2zSjiQ7_v4TMAKdiHm9T0"  # noqa: secret — тестовое значение


def _write_env(tmp_path, **values) -> Path:
    env = tmp_path / ".env"
    env.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    return env


def test_check_token_ok_and_masked(tmp_path):
    env = _write_env(tmp_path, BOT_TOKEN=TOKEN)
    result = doctor.check_token(doctor.parse_env(env.read_text()))
    assert result.ok
    assert TOKEN not in result.detail
    assert "1234" in result.detail


def test_check_token_rejects_placeholder(tmp_path):
    env = _write_env(tmp_path, BOT_TOKEN="your_bot_token_here")
    result = doctor.check_token(doctor.parse_env(env.read_text()))
    assert not result.ok
    assert "set-token" in result.detail


def test_check_admins_requires_at_least_one_id():
    assert doctor.check_admins({"ADMIN_USER_IDS": "[123]"}).ok
    assert doctor.check_admins({"ADMIN_USER_IDS": "123,456"}).ok
    assert not doctor.check_admins({"ADMIN_USER_IDS": "[]"}).ok
    assert doctor.check_admins({"ADMIN_USER_IDS": '["123456789"]'}).ok
    assert not doctor.check_admins({}).ok


def test_check_env_file_missing(tmp_path):
    result = doctor.check_env_file(tmp_path / ".env")
    assert not result.ok
    assert "init" in result.detail


def test_check_command_reports_missing_binary():
    result = doctor.check_command("definitely-not-a-real-binary-xyz", "Docker")
    assert not result.ok


def test_run_all_marks_failure_when_required_check_fails(tmp_path):
    _write_env(tmp_path, BOT_TOKEN="your_bot_token_here", ADMIN_USER_IDS="[1]")
    report = doctor.run_all(tmp_path, online=False, runner=lambda cmd: (0, "ok"))
    assert report["ok"] is False
    failed = [c["name"] for c in report["checks"] if not c["ok"]]
    assert "BOT_TOKEN" in failed


def test_run_all_ok_with_valid_env_and_docker(tmp_path):
    _write_env(tmp_path, BOT_TOKEN=TOKEN, ADMIN_USER_IDS="[1]")
    report = doctor.run_all(tmp_path, online=False, runner=lambda cmd: (0, "Docker version 27"))
    assert report["ok"] is True


def test_main_json_output_and_exit_code(tmp_path, capsys):
    _write_env(tmp_path, BOT_TOKEN="your_bot_token_here", ADMIN_USER_IDS="[1]")
    code = doctor.main(["--root", str(tmp_path), "--json", "--offline"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["ok"] is False
    assert TOKEN not in json.dumps(out)


def test_check_admins_accepts_usernames():
    assert doctor.check_admins({"ADMIN_USER_IDS": "[]", "ADMIN_USERNAMES": '["artem"]'}).ok
    assert doctor.check_admins({"ADMIN_USERNAMES": "@artem"}).ok
    assert not doctor.check_admins({"ADMIN_USER_IDS": "[]", "ADMIN_USERNAMES": "[]"}).ok


# ── сервер ───────────────────────────────────────────────────────

def test_check_server_not_configured(tmp_path):
    result = doctor.check_server(tmp_path)
    assert not result.ok and not result.required
    assert "set-server" in result.detail


def test_check_server_configured_is_masked(tmp_path):
    import server_config as sc
    cfg = sc.ServerConfig("123.45.67.89", 22, "root", "deploy_key", "/root/x")
    sc.save(tmp_path, cfg)
    (tmp_path / ".deploy" / "deploy_key").write_text("k")
    result = doctor.check_server(tmp_path)
    assert result.ok
    assert "root@123.45.•.•" in result.detail and "67.89" not in result.detail


def test_check_server_reports_missing_key(tmp_path):
    import server_config as sc
    sc.save(tmp_path, sc.ServerConfig("1.2.3.4", 22, "root", "deploy_key", "/root/x"))
    result = doctor.check_server(tmp_path)
    assert not result.ok and "set-server" in result.detail
