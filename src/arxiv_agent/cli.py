from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import typer

from .config import load_keyword_rules, load_settings

app = typer.Typer(help="arXiv monitoring and summarization agent")


def _resolve_lookback_hours(default_hours: int, days: int, months: int, years: float) -> int:
    if days < 0 or months < 0 or years < 0:
        raise typer.BadParameter("days/months/years must be non-negative")
    if days == 0 and months == 0 and years == 0:
        return default_hours

    total_days = days + months * 30 + years * 365
    return max(1, int(total_days * 24))


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
    from .arxiv_client import ArxivClient
    from .filtering import filter_and_rank
    from .models import ScoredPaper, SummaryResult
    from .notifier import Notifier
    from .semantic import SemanticMatcher
    from .summarizer import Summarizer

    s = load_settings(settings)
    r = load_keyword_rules(keywords)
    if not r.profiles:
        raise typer.BadParameter("No profiles found in keywords file")

    selected_profiles = r.profiles
    if profile:
        target = set(profile)
        selected_profiles = [p for p in r.profiles if p.name in target]
        missing = sorted(target - {p.name for p in selected_profiles})
        if missing:
            raise typer.BadParameter(f"Unknown profile(s): {', '.join(missing)}")

    lookback_hours = _resolve_lookback_hours(s.lookback_hours, days=days, months=months, years=years)
    client = ArxivClient(user_agent=s.user_agent, timeout_seconds=s.request_timeout_seconds)
    papers = client.fetch_recent(
        categories=r.categories,
        max_results_per_category=max_results_per_category,
        lookback_hours=lookback_hours,
    )

    summarizer = Summarizer(s.openai)
    semantic_matcher = SemanticMatcher(s.openai)
    notifier = Notifier(s.notify)

    items: list[tuple[ScoredPaper, SummaryResult]] = []
    for p in selected_profiles:
        profile_for_search = replace(p, max_items_per_run=top_k)
        semantic_scores = semantic_matcher.score_papers(papers, profile_for_search.semantic_queries)
        ranked = filter_and_rank(papers, profile_for_search, semantic_scores=semantic_scores)
        for scored in ranked:
            summary = summarizer.summarize(scored.paper)
            items.append((scored, summary))

    title = (
        f"arXiv 搜索结果 (window={lookback_hours / 24:.1f} days, "
        f"profiles={','.join(p.name for p in selected_profiles)})"
    )
    digest = notifier.format_digest(items, title=title, empty_message="该时间窗口内无命中论文。")
    typer.echo(digest)
    typer.echo(f"Fetched={len(papers)} Matched={len(items)}")


if __name__ == "__main__":
    app()
