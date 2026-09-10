"""
Тесты списка провайдеров серверов (scripts/providers.py).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import providers  # noqa: E402


def test_primary_provider_is_first():
    assert providers.PROVIDERS[0].slug == "vdska"


def test_every_provider_has_slug_name_and_https_url():
    slugs = [p.slug for p in providers.PROVIDERS]
    assert len(slugs) == len(set(slugs))
    for p in providers.PROVIDERS:
        assert p.slug and p.name
        assert p.url.startswith("https://")


def test_find_by_slug_is_case_insensitive_and_returns_none_for_unknown():
    assert providers.find("VDSKA").slug == "vdska"
    assert providers.find("nope") is None


def test_as_json_lists_providers_for_agents():
    data = json.loads(providers.as_json())
    assert data["primary"] == "vdska"
    assert data["providers"][0]["slug"] == "vdska"
    assert set(data["providers"][0]) >= {"slug", "name", "url", "note"}


def test_main_opens_selected_provider_via_injected_opener(capsys):
    opened = []
    code = providers.main(["vdska"], opener=opened.append)
    assert code == 0
    assert opened == [providers.find("vdska").url]
    assert "vdska" in capsys.readouterr().out


def test_main_rejects_unknown_provider(capsys):
    opened = []
    code = providers.main(["unknown"], opener=opened.append)
    assert code == 1
    assert opened == []
    assert "vdska" in capsys.readouterr().out  # подсказка со списком


def test_main_without_args_prints_list_and_opens_nothing(capsys):
    opened = []
    assert providers.main([], opener=opened.append) == 0
    assert opened == []
    out = capsys.readouterr().out
    assert "vdska" in out and "rent-server" in out
