"""
Тесты сканера секретов (scripts/check_secrets.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_secrets  # noqa: E402

TOKEN = "123456789:AAHfiqksKZ8WmR2zSjiQ7_v4TMAKdiHm9T0"  # noqa: secret — тестовое значение


def test_find_secrets_detects_bot_token_with_line_number():
    hits = check_secrets.find_secrets(f"x = 1\ntoken = '{TOKEN}'\n")
    assert len(hits) == 1
    assert hits[0].line == 2
    assert TOKEN not in hits[0].masked


def test_find_secrets_skips_lines_marked_noqa():
    hits = check_secrets.find_secrets(f"TOKEN = '{TOKEN}'  # noqa: secret\n")
    assert hits == []


def test_find_secrets_detects_hardcoded_password_assignment():
    hits = check_secrets.find_secrets('POSTGRES_PASSWORD = "Sup3rSecretValue!"\n')  # noqa: secret
    assert len(hits) == 1


def test_find_secrets_ignores_shell_variable_substitutions():
    text = (
        "POSTGRES_PASSWORD=$POSTGRES_PASSWORD\n"
        "REDIS_PASSWORD=${PROD_REDIS_PASSWORD}\n"
        "set DB_PASSWORD=%DB_PASSWORD%\n"
    )
    assert check_secrets.find_secrets(text) == []


def test_find_secrets_ignores_type_annotations_and_make_targets():
    text = (
        "_known_secrets: list[str] = []\n"
        "extra_secrets: Optional[Iterable[str]] = None\n"
        "check-secrets: _check-python\n"
    )
    assert check_secrets.find_secrets(text) == []


def test_scan_paths_allows_example_passwords_in_docs_but_not_tokens(tmp_path):
    (tmp_path / "README.md").write_text("POSTGRES_PASSWORD=securepassword\n")
    (tmp_path / "GUIDE.md").write_text(f"BOT_TOKEN={TOKEN}\n")
    findings = check_secrets.scan_paths([tmp_path / "README.md", tmp_path / "GUIDE.md"])
    assert [f.path.name for f in findings] == ["GUIDE.md"]


def test_find_secrets_ignores_placeholders_and_lookups():
    text = (
        'POSTGRES_PASSWORD=CHANGE_ME_TO_STRONG_PASSWORD_123!\n'
        'password = os.environ["POSTGRES_PASSWORD"]\n'
        'postgres_password: str = Field("", alias="POSTGRES_PASSWORD")\n'
    )
    assert check_secrets.find_secrets(text) == []


def test_scan_paths_skips_env_files_and_venv(tmp_path):
    (tmp_path / ".env").write_text(f"BOT_TOKEN={TOKEN}\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "x.py").write_text(f"t='{TOKEN}'\n")
    (tmp_path / "bad.py").write_text(f"t='{TOKEN}'\n")

    findings = check_secrets.scan_paths([tmp_path / ".env", tmp_path / ".venv" / "x.py", tmp_path / "bad.py"])

    assert [f.path.name for f in findings] == ["bad.py"]


def test_main_returns_1_when_secret_found(tmp_path, capsys):
    (tmp_path / "bad.py").write_text(f"t='{TOKEN}'\n")
    code = check_secrets.main(["--paths", str(tmp_path / "bad.py")])
    assert code == 1
    assert TOKEN not in capsys.readouterr().out


def test_main_returns_0_when_clean(tmp_path):
    (tmp_path / "ok.py").write_text("print('hello')\n")
    assert check_secrets.main(["--paths", str(tmp_path / "ok.py")]) == 0
