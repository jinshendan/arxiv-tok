from pathlib import Path

import pytest
import typer

from arxiv_agent.cli import (
    _parse_last_window,
    _resolve_keywords_path,
    _resolve_settings_path,
)


def test_parse_last_window() -> None:
    assert _parse_last_window("7d") == (7, 0, 0.0)
    assert _parse_last_window("2w") == (14, 0, 0.0)
    assert _parse_last_window("3m") == (0, 3, 0.0)
    assert _parse_last_window("1y") == (0, 0, 1.0)


@pytest.mark.parametrize("value", ["0d", "abc", "10q"])
def test_parse_last_window_invalid(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        _parse_last_window(value)


def test_resolve_settings_prefers_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/settings.local.yaml").write_text("a: 1\n", encoding="utf-8")
    (tmp_path / "config/settings.yaml").write_text("b: 2\n", encoding="utf-8")

    resolved = _resolve_settings_path(None)
    assert resolved == Path("config/settings.local.yaml")


def test_resolve_keywords_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "my_keywords.yaml"
    p.write_text("profiles: []\n", encoding="utf-8")
    monkeypatch.setenv("ARXIV_AGENT_KEYWORDS", str(p))

    resolved = _resolve_keywords_path(None)
    assert resolved == p
