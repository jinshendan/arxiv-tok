from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class OpenAIConfig:
    enabled: bool = False
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "gpt-5-mini"
    embedding_model: str = "text-embedding-3-large"
    timeout_seconds: int = 60


@dataclass
class NotifyEmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password_env: str = "SMTP_PASSWORD"
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)
    use_tls: bool = True


@dataclass
class NotifyTelegramConfig:
    enabled: bool = False
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id: str = ""


@dataclass
class NotifyConfig:
    console: bool = True
    email: NotifyEmailConfig = field(default_factory=NotifyEmailConfig)
    telegram: NotifyTelegramConfig = field(default_factory=NotifyTelegramConfig)


@dataclass
class ScheduleConfig:
    timezone: str = "Europe/Paris"
    hour: int = 8
    minute: int = 0


@dataclass
class Settings:
    database_path: str = "data/arxiv_agent.db"
    lookback_hours: int = 30
    max_results_per_category: int = 150
    request_timeout_seconds: int = 30
    user_agent: str = "arxiv-agent/0.1"
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)


@dataclass
class KeywordProfile:
    name: str
    include_all: list[str] = field(default_factory=list)
    include_any: list[str] = field(default_factory=list)
    exclude_any: list[str] = field(default_factory=list)
    semantic_queries: list[str] = field(default_factory=list)
    semantic_min_similarity: float = 0.35
    semantic_weight: int = 2
    min_score: int = 1
    max_items_per_run: int = 10


@dataclass
class KeywordRules:
    categories: list[str] = field(default_factory=lambda: ["cs.LG", "cs.CL"])
    profiles: list[KeywordProfile] = field(default_factory=list)


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return data


def load_settings(path: str | Path) -> Settings:
    data = _read_yaml(Path(path))

    openai_data = data.get("openai", {})
    notify_data = data.get("notify", {})
    email_data = notify_data.get("email", {})
    telegram_data = notify_data.get("telegram", {})
    schedule_data = data.get("schedule", {})

    return Settings(
        database_path=data.get("database_path", "data/arxiv_agent.db"),
        lookback_hours=int(data.get("lookback_hours", 30)),
        max_results_per_category=int(data.get("max_results_per_category", 150)),
        request_timeout_seconds=int(data.get("request_timeout_seconds", 30)),
        user_agent=data.get("user_agent", "arxiv-agent/0.1"),
        openai=OpenAIConfig(
            enabled=bool(openai_data.get("enabled", False)),
            api_key_env=openai_data.get("api_key_env", "OPENAI_API_KEY"),
            model=openai_data.get("model", "gpt-5-mini"),
            embedding_model=openai_data.get("embedding_model", "text-embedding-3-large"),
            timeout_seconds=int(openai_data.get("timeout_seconds", 60)),
        ),
        notify=NotifyConfig(
            console=bool(notify_data.get("console", True)),
            email=NotifyEmailConfig(
                enabled=bool(email_data.get("enabled", False)),
                smtp_host=email_data.get("smtp_host", ""),
                smtp_port=int(email_data.get("smtp_port", 587)),
                username=email_data.get("username", ""),
                password_env=email_data.get("password_env", "SMTP_PASSWORD"),
                from_addr=email_data.get("from_addr", ""),
                to_addrs=list(email_data.get("to_addrs", [])),
                use_tls=bool(email_data.get("use_tls", True)),
            ),
            telegram=NotifyTelegramConfig(
                enabled=bool(telegram_data.get("enabled", False)),
                bot_token_env=telegram_data.get("bot_token_env", "TELEGRAM_BOT_TOKEN"),
                chat_id=telegram_data.get("chat_id", ""),
            ),
        ),
        schedule=ScheduleConfig(
            timezone=schedule_data.get("timezone", "Europe/Paris"),
            hour=int(schedule_data.get("hour", 8)),
            minute=int(schedule_data.get("minute", 0)),
        ),
    )


def load_keyword_rules(path: str | Path) -> KeywordRules:
    data = _read_yaml(Path(path))
    profiles: list[KeywordProfile] = []
    for raw in data.get("profiles", []) or []:
        profiles.append(
            KeywordProfile(
                name=raw["name"],
                include_all=list(raw.get("include_all", [])),
                include_any=list(raw.get("include_any", [])),
                exclude_any=list(raw.get("exclude_any", [])),
                semantic_queries=list(raw.get("semantic_queries", [])),
                semantic_min_similarity=float(raw.get("semantic_min_similarity", 0.35)),
                semantic_weight=int(raw.get("semantic_weight", 2)),
                min_score=int(raw.get("min_score", 1)),
                max_items_per_run=int(raw.get("max_items_per_run", 10)),
            )
        )
    return KeywordRules(categories=list(data.get("categories", ["cs.LG", "cs.CL"])), profiles=profiles)
