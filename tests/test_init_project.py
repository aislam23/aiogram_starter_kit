"""
Тесты неинтерактивной инициализации проекта (scripts/init_project.py).
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import init_project  # noqa: E402

TEMPLATE_FILES = [
    ".env.example", ".env.prod.example", "docker-compose.yml", "docker-compose.prod.yml",
    "justfile", "Makefile", "README.md", "app/__init__.py",
]


@pytest.fixture
def project(tmp_path) -> Path:
    """Копия файлов шаблона, которые трогает init."""
    for rel in TEMPLATE_FILES:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dst)
    return tmp_path


def _env(path: Path) -> dict:
    return init_project.parse_env(path.read_text())


def test_slugify_makes_safe_identifier():
    assert init_project.slugify("My Cool Bot!") == "my_cool_bot"
    assert init_project.slugify("already_ok") == "already_ok"


def test_apply_writes_env_with_project_values(project):
    init_project.apply(project, init_project.ProjectConfig(name="my_bot", admin_id=123))

    env = _env(project / ".env")
    assert env["ADMIN_USER_IDS"] == "[123]"
    assert env["POSTGRES_DB"] == "my_bot_db"
    assert env["POSTGRES_USER"] == "my_bot_user"
    assert len(env["POSTGRES_PASSWORD"]) >= 15
    assert env["EXAMPLE_HANDLERS"] == "true"
    assert env["BOT_TOKEN"] == "your_bot_token_here"  # токен ставится отдельно через set_token


def test_apply_writes_prod_env_with_own_passwords(project):
    init_project.apply(project, init_project.ProjectConfig(name="my_bot", admin_id=123))

    dev, prod = _env(project / ".env"), _env(project / ".env.prod")
    assert prod["POSTGRES_DB"] == "my_bot_db_prod"
    assert prod["POSTGRES_PASSWORD"] != dev["POSTGRES_PASSWORD"]
    assert len(prod["REDIS_PASSWORD"]) >= 15
    assert prod["ENV"] == "production"
    assert prod["EXAMPLE_HANDLERS"] == "false"
    assert prod["ADMIN_USER_IDS"] == "[123]"


def test_apply_preserves_existing_token_and_copies_it_to_prod(project):
    (project / ".env").write_text("BOT_TOKEN=111:existing_token_value_here_XXXXXXXXXXXXXXX\nBOT_USERNAME=old_bot\n")

    init_project.apply(project, init_project.ProjectConfig(name="my_bot", admin_id=123))

    assert _env(project / ".env")["BOT_TOKEN"] == "111:existing_token_value_here_XXXXXXXXXXXXXXX"
    assert _env(project / ".env")["BOT_USERNAME"] == "old_bot"
    assert _env(project / ".env.prod")["BOT_TOKEN"] == "111:existing_token_value_here_XXXXXXXXXXXXXXX"


def test_apply_does_not_regenerate_passwords_on_rerun(project):
    cfg = init_project.ProjectConfig(name="my_bot", admin_id=123)
    init_project.apply(project, cfg)
    first = _env(project / ".env")["POSTGRES_PASSWORD"]
    init_project.apply(project, cfg)
    assert _env(project / ".env")["POSTGRES_PASSWORD"] == first


def test_apply_renames_docker_resources(project):
    init_project.apply(project, init_project.ProjectConfig(name="my_bot", admin_id=123))

    compose = (project / "docker-compose.yml").read_text()
    assert "container_name: my_bot_bot_dev" in compose
    assert "container_name: my_bot_postgres_dev" in compose
    assert "aiogram_" not in compose.replace("aiogram/telegram-bot-api", "")
    assert 'project_name := "my_bot"' in (project / "justfile").read_text()
    assert "PROJECT_NAME = my_bot" in (project / "Makefile").read_text()
    assert "container_name: my_bot_bot_prod" in (project / "docker-compose.prod.yml").read_text()


def test_apply_changes_ports_when_given(project):
    init_project.apply(project, init_project.ProjectConfig(
        name="my_bot", admin_id=123, postgres_port=5433, pgadmin_port=8081,
    ))
    compose = (project / "docker-compose.yml").read_text()
    assert '"5433:5432"' in compose
    assert '"8081:80"' in compose


def test_apply_updates_metadata_and_readme(project):
    init_project.apply(project, init_project.ProjectConfig(
        name="my_bot", admin_id=123, description="Бот для заметок", author="Артём",
    ))
    assert 'Бот для заметок' in (project / "app/__init__.py").read_text()
    assert '__author__ = "Артём"' in (project / "app/__init__.py").read_text()
    assert (project / "README.md").read_text().startswith("# 🤖 my_bot")


def test_apply_is_idempotent(project):
    cfg = init_project.ProjectConfig(name="my_bot", admin_id=123, description="Бот", author="A")
    init_project.apply(project, cfg)
    snapshot = {f: (project / f).read_text() for f in TEMPLATE_FILES + [".env", ".env.prod"]}
    init_project.apply(project, cfg)
    assert {f: (project / f).read_text() for f in snapshot} == snapshot


def test_main_fails_clearly_without_required_args_and_tty(project, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    code = init_project.main(["--root", str(project)])
    assert code == 2
    assert "--name" in capsys.readouterr().err


def test_main_json_reports_changed_files_and_next_steps(project, capsys):
    code = init_project.main(["--root", str(project), "--name", "my_bot", "--admin-id", "123", "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert ".env" in report["written"]
    assert any("set-token" in step for step in report["next_steps"])


# ── админ по username ────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("123456789", (123456789, None)),
    ("@artem", (None, "artem")),
    ("Artem", (None, "artem")),
    ("https://t.me/artem", (None, "artem")),
    ("t.me/Artem_1", (None, "artem_1")),
])
def test_parse_admin_detects_id_or_username(raw, expected):
    assert init_project.parse_admin(raw) == expected


def test_parse_admin_rejects_garbage():
    with pytest.raises(ValueError):
        init_project.parse_admin("ar tem!")


def test_apply_writes_admin_username_when_given(project):
    init_project.apply(project, init_project.ProjectConfig(name="my_bot", admin_username="Artem"))

    env = _env(project / ".env")
    assert env["ADMIN_USER_IDS"] == "[]"
    assert env["ADMIN_USERNAMES"] == '["artem"]'
    assert _env(project / ".env.prod")["ADMIN_USERNAMES"] == '["artem"]'


def test_main_accepts_admin_username_via_admin_flag(project, capsys):
    code = init_project.main(["--root", str(project), "--name", "my_bot", "--admin", "@artem", "--json"])
    assert code == 0
    assert _env(project / ".env")["ADMIN_USERNAMES"] == '["artem"]'


def test_main_accepts_admin_id_via_admin_flag(project):
    assert init_project.main(["--root", str(project), "--name", "my_bot", "--admin", "42", "--json"]) == 0
    assert _env(project / ".env")["ADMIN_USER_IDS"] == "[42]"


def test_project_config_requires_id_or_username():
    with pytest.raises(ValueError):
        init_project.ProjectConfig(name="my_bot")
