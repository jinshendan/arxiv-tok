from pathlib import Path

from arxiv_agent.config import load_settings
from arxiv_agent.llm_provider import LLMProviderClient


def test_load_settings_model_block(tmp_path: Path) -> None:
    p = tmp_path / "settings.yaml"
    p.write_text(
        """
model:
  enabled: true
  provider: ollama
  base_url: http://127.0.0.1:11434
  require_api_key: false
  model: qwen2.5:7b
  embedding_model: nomic-embed-text
""",
        encoding="utf-8",
    )
    s = load_settings(p)
    assert s.model.enabled is True
    assert s.model.provider == "ollama"
    assert s.model.require_api_key is False


def test_load_settings_legacy_openai_block(tmp_path: Path) -> None:
    p = tmp_path / "settings.yaml"
    p.write_text(
        """
openai:
  enabled: true
  model: gpt-5-mini
  embedding_model: text-embedding-3-large
""",
        encoding="utf-8",
    )
    s = load_settings(p)
    assert s.model.enabled is True
    assert s.model.provider == "openai"
    assert s.model.model == "gpt-5-mini"


def test_llm_provider_chat_enabled_for_ollama_without_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = tmp_path / "settings.yaml"
    p.write_text(
        """
model:
  enabled: true
  provider: ollama
  base_url: http://127.0.0.1:11434
  require_api_key: false
  model: qwen2.5:7b
  embedding_model: nomic-embed-text
""",
        encoding="utf-8",
    )
    client = LLMProviderClient(load_settings(p).model)
    assert client.chat_enabled is True
    assert client.embedding_enabled is True


def test_llm_provider_chat_enabled_openai_requires_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = tmp_path / "settings.yaml"
    p.write_text(
        """
model:
  enabled: true
  provider: openai
  api_key_env: OPENAI_API_KEY
  model: gpt-5-mini
""",
        encoding="utf-8",
    )
    cfg = load_settings(p).model
    client = LLMProviderClient(cfg)
    assert client.chat_enabled is False
