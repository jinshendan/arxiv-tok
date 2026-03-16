from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

import httpx
import typer

from .config import load_keyword_rules, load_settings
from .notifier import Notifier
from .search_service import run_search

app = typer.Typer(help="arXiv monitoring and summarization agent")

SETTINGS_ENV = "ARXIV_AGENT_SETTINGS"
KEYWORDS_ENV = "ARXIV_AGENT_KEYWORDS"


def _resolve_path(
    *,
    user_value: Path | None,
    env_name: str,
    default_candidates: list[Path],
    label: str,
) -> Path:
    if user_value is not None:
        if user_value.exists():
            return user_value
        raise typer.BadParameter(f"{label} file not found: {user_value}")

    env_value = os.getenv(env_name, "").strip()
    if env_value:
        env_path = Path(env_value)
        if env_path.exists():
            return env_path
        raise typer.BadParameter(f"{label} file from ${env_name} not found: {env_path}")

    for p in default_candidates:
        if p.exists():
            return p
    raise typer.BadParameter(
        f"{label} file not found. Checked: {', '.join(str(p) for p in default_candidates)}"
    )


def _resolve_settings_path(settings: Path | None) -> Path:
    return _resolve_path(
        user_value=settings,
        env_name=SETTINGS_ENV,
        default_candidates=[Path("config/settings.local.yaml"), Path("config/settings.yaml")],
        label="settings",
    )


def _resolve_keywords_path(keywords: Path | None) -> Path:
    return _resolve_path(
        user_value=keywords,
        env_name=KEYWORDS_ENV,
        default_candidates=[Path("config/keywords.local.yaml"), Path("config/keywords.yaml")],
        label="keywords",
    )


def _parse_last_window(last: str) -> tuple[int, int, float]:
    token = last.strip().lower()
    m = re.fullmatch(r"(\d+)\s*([dwmy])", token)
    if not m:
        raise typer.BadParameter("Invalid --last format. Use 7d / 2w / 3m / 1y")
    value = int(m.group(1))
    unit = m.group(2)
    if value <= 0:
        raise typer.BadParameter("--last value must be > 0")
    if unit == "d":
        return value, 0, 0.0
    if unit == "w":
        return value * 7, 0, 0.0
    if unit == "m":
        return 0, value, 0.0
    return 0, 0, float(value)


@app.command("init-db")
def init_db(
    settings: Path | None = typer.Option(
        None,
        "--settings",
        help="Settings file path. Auto-resolves config/settings.local.yaml then config/settings.yaml",
    )
) -> None:
    from .db import Database

    settings_path = _resolve_settings_path(settings)
    s = load_settings(settings_path)
    db = Database(s.database_path)
    db.init_schema()
    typer.echo(f"DB initialized at {s.database_path}")


@app.command("run")
def run(
    settings: Path | None = typer.Option(
        None,
        "--settings",
        help="Settings file path. Auto-resolves config/settings.local.yaml then config/settings.yaml",
    ),
    keywords: Path | None = typer.Option(
        None,
        "--keywords",
        help="Keywords file path. Auto-resolves config/keywords.local.yaml then config/keywords.yaml",
    ),
) -> None:
    from .pipeline import run_once

    settings_path = _resolve_settings_path(settings)
    keywords_path = _resolve_keywords_path(keywords)
    s = load_settings(settings_path)
    r = load_keyword_rules(keywords_path)
    if not r.profiles:
        raise typer.BadParameter("No profiles found in keywords file")
    result = run_once(s, r)
    typer.echo(
        f"Done. run_id={result.run_id} fetched={result.fetched} "
        f"matched={result.matched} channels={','.join(result.notified_channels)}"
    )


@app.command("schedule")
def schedule(
    settings: Path | None = typer.Option(
        None,
        "--settings",
        help="Settings file path. Auto-resolves config/settings.local.yaml then config/settings.yaml",
    ),
    keywords: Path | None = typer.Option(
        None,
        "--keywords",
        help="Keywords file path. Auto-resolves config/keywords.local.yaml then config/keywords.yaml",
    ),
) -> None:
    from .scheduler import run_scheduler

    settings_path = _resolve_settings_path(settings)
    keywords_path = _resolve_keywords_path(keywords)
    s = load_settings(settings_path)
    r = load_keyword_rules(keywords_path)
    if not r.profiles:
        raise typer.BadParameter("No profiles found in keywords file")
    run_scheduler(s, r)


@app.command("search")
def search(
    settings: Path | None = typer.Option(
        None,
        "--settings",
        help="Settings file path. Auto-resolves config/settings.local.yaml then config/settings.yaml",
    ),
    keywords: Path | None = typer.Option(
        None,
        "--keywords",
        help="Keywords file path. Auto-resolves config/keywords.local.yaml then config/keywords.yaml",
    ),
    last: str | None = typer.Option(
        None,
        "--last",
        help="Shorthand time window, e.g. 7d / 2w / 3m / 1y",
    ),
    days: int = typer.Option(0, min=0, help="Search papers from last N days"),
    months: int = typer.Option(0, min=0, help="Search papers from last N months (30d each)"),
    years: float = typer.Option(0.0, min=0.0, help="Search papers from last N years (365d each)"),
    profile: list[str] | None = typer.Option(
        None, "--profile", "-p", help="Profile name from keywords.yaml (repeatable)"
    ),
    top_k: int = typer.Option(
        10,
        "--top-k",
        "--limit",
        "-k",
        min=1,
        max=100,
        help="Top papers per profile",
    ),
    max_results_per_category: int = typer.Option(
        600,
        "--max-results-per-category",
        "--max-fetch",
        min=50,
        max=5000,
        help="Fetch limit per arXiv category for this search",
    ),
) -> None:
    settings_path = _resolve_settings_path(settings)
    keywords_path = _resolve_keywords_path(keywords)
    s = load_settings(settings_path)
    r = load_keyword_rules(keywords_path)

    resolved_days, resolved_months, resolved_years = days, months, years
    if last is not None:
        if days != 0 or months != 0 or years != 0.0:
            raise typer.BadParameter("Use either --last or --days/--months/--years, not both.")
        resolved_days, resolved_months, resolved_years = _parse_last_window(last)

    try:
        result = run_search(
            s,
            r,
            days=resolved_days,
            months=resolved_months,
            years=resolved_years,
            profile_names=profile,
            top_k=top_k,
            max_results_per_category=max_results_per_category,
        )
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise typer.BadParameter(
                "arXiv API 限流(429)。请降低 --max-results-per-category、缩短时间窗口，稍后重试。"
            ) from e
        raise

    notifier = Notifier(s.notify)
    title = (
        f"arXiv 搜索结果 (window={result.lookback_hours / 24:.1f} days, "
        f"profiles={','.join(result.selected_profiles)})"
    )
    digest = notifier.format_digest(result.items, title=title, empty_message="该时间窗口内无命中论文。")
    typer.echo(digest)
    typer.echo(f"Fetched={result.fetched} Matched={result.matched}")


@app.command("dashboard")
def dashboard(
    host: str = typer.Option("127.0.0.1", help="Dashboard host"),
    port: int = typer.Option(8501, min=1, max=65535, help="Dashboard port"),
) -> None:
    dashboard_file = Path(__file__).with_name("dashboard.py")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_file),
        "--server.address",
        host,
        "--server.port",
        str(port),
    ]
    raise typer.Exit(subprocess.call(cmd))


@app.command("paths")
def paths(
    settings: Path | None = typer.Option(None, "--settings", help="Optional settings path override"),
    keywords: Path | None = typer.Option(None, "--keywords", help="Optional keywords path override"),
) -> None:
    settings_path = _resolve_settings_path(settings)
    keywords_path = _resolve_keywords_path(keywords)
    typer.echo(f"settings: {settings_path}")
    typer.echo(f"keywords: {keywords_path}")
    typer.echo(f"{SETTINGS_ENV}: {os.getenv(SETTINGS_ENV, '(not set)')}")
    typer.echo(f"{KEYWORDS_ENV}: {os.getenv(KEYWORDS_ENV, '(not set)')}")


if __name__ == "__main__":
    app()
