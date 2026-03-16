from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import httpx
import typer

from .config import load_keyword_rules, load_settings
from .notifier import Notifier
from .search_service import run_search

app = typer.Typer(help="arXiv monitoring and summarization agent")


@app.command("init-db")
def init_db(settings: Path = typer.Option(Path("config/settings.yaml"), exists=True)) -> None:
    from .db import Database

    s = load_settings(settings)
    db = Database(s.database_path)
    db.init_schema()
    typer.echo(f"DB initialized at {s.database_path}")


@app.command("run")
def run(
    settings: Path = typer.Option(Path("config/settings.yaml"), exists=True),
    keywords: Path = typer.Option(Path("config/keywords.yaml"), exists=True),
) -> None:
    from .pipeline import run_once

    s = load_settings(settings)
    r = load_keyword_rules(keywords)
    if not r.profiles:
        raise typer.BadParameter("No profiles found in keywords file")
    result = run_once(s, r)
    typer.echo(
        f"Done. run_id={result.run_id} fetched={result.fetched} "
        f"matched={result.matched} channels={','.join(result.notified_channels)}"
    )


@app.command("schedule")
def schedule(
    settings: Path = typer.Option(Path("config/settings.yaml"), exists=True),
    keywords: Path = typer.Option(Path("config/keywords.yaml"), exists=True),
) -> None:
    from .scheduler import run_scheduler

    s = load_settings(settings)
    r = load_keyword_rules(keywords)
    if not r.profiles:
        raise typer.BadParameter("No profiles found in keywords file")
    run_scheduler(s, r)


@app.command("search")
def search(
    settings: Path = typer.Option(Path("config/settings.yaml"), exists=True),
    keywords: Path = typer.Option(Path("config/keywords.yaml"), exists=True),
    days: int = typer.Option(0, min=0, help="Search papers from last N days"),
    months: int = typer.Option(0, min=0, help="Search papers from last N months (30d each)"),
    years: float = typer.Option(0.0, min=0.0, help="Search papers from last N years (365d each)"),
    profile: list[str] | None = typer.Option(
        None, "--profile", "-p", help="Profile name from keywords.yaml (repeatable)"
    ),
    top_k: int = typer.Option(10, min=1, max=100, help="Top papers per profile"),
    max_results_per_category: int = typer.Option(
        600, min=50, max=5000, help="Fetch limit per arXiv category for this search"
    ),
) -> None:
    s = load_settings(settings)
    r = load_keyword_rules(keywords)
    try:
        result = run_search(
            s,
            r,
            days=days,
            months=months,
            years=years,
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


if __name__ == "__main__":
    app()
